"""KuralCheck developer API: the backend for the Chrome extension (and any script).

    uv run uvicorn kuralcheck.api:app --port 8765

The Gnani key stays on this server; the extension only talks to it. Endpoints:

GET  /health                 server status, key configured, noise clips, fix layer size
GET  /v1/results/latest      headline numbers from the latest benchmark run (0 API calls)
POST /v1/score               CER/WER/number accuracy for your own reference + transcript (0 API calls)
POST /v1/fix                 run the KuralCheck fix layer on a Prisma transcript (0 API calls)
POST /v1/test-text           up to 10 sentences: Timbre -> clean + noisy phone -> Prisma F0/F3
POST /v1/test-audio          your recording: clean vs noisy phone line, Prisma F0/F3 (never stored)

Optional auth: set KURALCHECK_API_TOKEN and send `Authorization: Bearer <token>`.
Paid calls are cached, paced by the shared adaptive throttle and capped per day.
"""

import base64
import json
import os
import secrets
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from kuralcheck.audio.conditions import CONDITIONS, NoiseBank
from kuralcheck.cache import Cache
from kuralcheck.clients.errors import ApiError
from kuralcheck.clients.prisma import PrismaClient
from kuralcheck.clients.timbre import TAMIL_VOICES_V25, TimbreClient
from kuralcheck.config import get_settings
from kuralcheck.data import NOISE_DIR
from kuralcheck.fixlayer.bias import load_bias_words
from kuralcheck.fixlayer.lexicon import load_lexicon
from kuralcheck.metrics import score_utterance
from kuralcheck.report.runs import latest
from kuralcheck.text.normalize import normalize
from kuralcheck.throttle import shared_throttle
from kuralcheck.webapp import (
    DEFAULT_DAILY_CALL_CAP,
    MAX_SENTENCES,
    DailyCap,
    parse_sentences,
    run_sentence_job,
    run_voice_job,
)

MAX_UPLOAD_BYTES = 16 * 1024 * 1024
VERSION = "1.0.0"

app = FastAPI(title="KuralCheck API", version=VERSION, description=__doc__)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://[a-p]{32}|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- shared state (overridable in tests) ------------------------------------------


class State:
    def __init__(self) -> None:
        s = get_settings()
        self.key = s.gnani_api_key.get_secret_value()
        self.tts_model = s.tts_model
        self.cache = Cache(s.cache_path)
        self.throttle = shared_throttle(s.gnani_calls_per_second, s.gnani_max_calls_per_second)
        self.noise = NoiseBank.load(NOISE_DIR)
        self.bias = load_bias_words()
        self.lexicon = load_lexicon()
        self.cap = DailyCap(limit=int(os.environ.get("DAILY_CALL_CAP", DEFAULT_DAILY_CALL_CAP)))
        self.token = os.environ.get("KURALCHECK_API_TOKEN", "")

    def timbre(self) -> Any:
        return TimbreClient(self.key, self.cache, throttle=self.throttle)

    def prisma(self, cached: bool = True) -> Any:
        return PrismaClient(self.key, self.cache if cached else None, throttle=self.throttle)


@lru_cache(maxsize=1)
def get_state() -> State:
    return State()


def auth(authorization: str = Header(default=""), state: State = Depends(get_state)) -> State:
    if state.token and not secrets.compare_digest(authorization, f"Bearer {state.token}"):
        raise HTTPException(401, "Missing or wrong API token (Settings → API token in the extension).")
    return state


def need_key(state: State) -> None:
    if not state.key:
        raise HTTPException(503, "GNANI_API_KEY is not set on the KuralCheck server.")


def _b64(audio: bytes) -> str:
    return "data:audio/wav;base64," + base64.b64encode(audio).decode("ascii")


# --- models ------------------------------------------------------------------------


class ScoreIn(BaseModel):
    reference: str = Field(..., max_length=2000)
    hypothesis: str = Field(..., max_length=2000)
    accepted_variants: list[str] = Field(default_factory=list, max_length=50)


class FixIn(BaseModel):
    text: str = Field(..., max_length=4000)


class TextTestIn(BaseModel):
    sentences: list[str] = Field(..., min_length=1, max_length=MAX_SENTENCES)
    voice: str = "Asmita"
    include_audio: bool = True


# --- endpoints ---------------------------------------------------------------------


@app.get("/health")
def health(state: State = Depends(get_state)) -> dict[str, Any]:
    return {
        "status": "ok",
        "version": VERSION,
        "gnani_key_configured": bool(state.key),
        "auth_required": bool(state.token),
        "noise_clips": [n for n, _ in state.noise.clips],
        "fix_layer": {"bias_words": len(state.bias), "word_rules": len(state.lexicon.rules),
                      "format_rules": len(state.lexicon.format_rules)},  # fmt: skip
        "voices": list(TAMIL_VOICES_V25),
        "daily_calls_left": max(0, state.cap.limit - state.cap.used),
    }


@app.get("/v1/results/latest")
def results_latest(split: str = "test", _: State = Depends(auth)) -> dict[str, Any]:
    run = latest(split) or latest(None)
    if run is None:
        raise HTTPException(404, "No benchmark results yet.")
    card = run.path / "scorecard.json"
    return {
        "run": run.name,
        "split": run.split,
        "meta": {k: run.summary["run"].get(k) for k in ("created_at", "models", "n_utterances", "latency_ms", "prisma_calls")},
        "scorecard": json.loads(card.read_text(encoding="utf-8")) if card.exists() else None,
        "overall": [
            {k: r[k] for k in ("source", "condition", "setting", "n", "cer", "wer", "number_accuracy", "failures")}
            for r in run.summary["overall"]
        ],
    }


@app.post("/v1/score")
def score(body: ScoreIn, _: State = Depends(auth)) -> dict[str, Any]:
    if not normalize(body.reference):
        raise HTTPException(422, "The reference is empty after normalisation (send UTF-8 text).")
    sc = score_utterance(body.reference, body.hypothesis, body.accepted_variants)
    return {
        "cer": sc.char_edits / sc.char_ref if sc.char_ref else 0.0,
        "wer": sc.word_edits / sc.word_ref if sc.word_ref else 0.0,
        "char_edits": sc.char_edits,
        "word_edits": sc.word_edits,
        "numbers": {"matched": sc.num_matched, "in_reference": sc.num_ref},
        "reference_used": sc.reference,
        "hypothesis_normalised": sc.hypothesis,
        "api_calls": 0,
    }


@app.post("/v1/fix")
def fix(body: FixIn, state: State = Depends(auth)) -> dict[str, Any]:
    text, hits = state.lexicon.apply_with_hits(body.text)
    return {"text": text, "rules_applied": hits, "api_calls": 0}


@app.post("/v1/test-text")
def test_text(body: TextTestIn, state: State = Depends(auth)) -> dict[str, Any]:
    need_key(state)
    sentences, problems = parse_sentences("\n".join(body.sentences))
    if problems:
        raise HTTPException(422, " ".join(problems))
    if body.voice not in TAMIL_VOICES_V25:
        raise HTTPException(422, f"voice must be one of {TAMIL_VOICES_V25}")
    if not state.cap.try_spend(5 * len(set(sentences))):
        raise HTTPException(429, "Daily API budget used up on this server.")
    try:
        report = run_sentence_job(sentences, body.voice, state.tts_model, state.timbre(), state.prisma(),
                                  state.noise, state.bias, state.lexicon)  # fmt: skip
    except ApiError as exc:
        raise HTTPException(502, f"Gnani API error: {exc}") from None
    clean, noisy = report["conditions"]
    rows = []
    for r in report["rows"]:
        row = {k: v for k, v in r.items() if k != "audio"}
        if body.include_audio:
            row["audio"] = {c: _b64(a) for c, a in r["audio"].items()}
        rows.append(row)
    return {
        "conditions": {c: CONDITIONS[c].label for c in (clean, noisy)},
        "overall_cer": report["overall_cer"],
        "n": report["n"],
        "rows": rows,
        "stats": report["stats"],
    }


@app.post("/v1/test-audio")
async def test_audio(
    file: UploadFile = File(...),
    reference: str = Form(default=""),
    state: State = Depends(auth),
) -> dict[str, Any]:
    need_key(state)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Recording is larger than 16 MB.")
    if not state.cap.try_spend(4):
        raise HTTPException(429, "Daily API budget used up on this server.")
    try:
        result = run_voice_job(data, file.filename or "voice.webm", state.prisma(cached=False), state.noise,
                               reference, bias_words=state.bias, lexicon=state.lexicon)  # fmt: skip
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except ApiError as exc:
        raise HTTPException(502, f"Gnani API error: {exc}") from None
    finally:
        del data  # never kept
    audio = result.pop("audio")
    result["audio"] = {c: _b64(a) for c, a in audio.items()}
    result["conditions"] = {c: CONDITIONS[c].label for c in audio}
    return result

