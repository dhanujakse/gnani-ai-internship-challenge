"""Logic behind the Streamlit app, kept out of the pages so it can be unit-tested.

The app never runs the full benchmark: it reads results/ and runs small user jobs
(<= 10 sentences, rate-limited per session and per day). User audio is never stored:
it lives in a temp dir for the request and is not cached.
"""

import html
import io
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import soundfile as sf

from kuralcheck.audio.conditions import CONDITIONS, NoiseBank, build_condition, load_clean
from kuralcheck.clients.prisma import PrismaSettings
from kuralcheck.clients.timbre import TimbreSettings
from kuralcheck.fixlayer.lexicon import Lexicon
from kuralcheck.metrics import corpus_cer, score_utterance
from kuralcheck.runner import BIAS_SCORE

MAX_SENTENCES = 10
MAX_SENTENCE_CHARS = 200
MAX_VOICE_SECONDS = 30
SENTENCE_RUNS_PER_SESSION = 3
VOICE_RUNS_PER_SESSION = 5
DEFAULT_DAILY_CALL_CAP = 400
_TAMIL = re.compile(r"[஀-௿]")


def get_secret(name: str, default: str = "") -> str:
    """Streamlit secrets first (hosted app), then environment / .env (local)."""
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    if name in os.environ:
        return os.environ[name]
    from kuralcheck.config import get_settings

    value = getattr(get_settings(), name.lower(), default)
    return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value or default)


# --- limits -------------------------------------------------------------------------


def session_allows(state: MutableMapping[str, Any], key: str, limit: int) -> bool:
    return int(state.get(key, 0)) < limit


def session_count(state: MutableMapping[str, Any], key: str) -> None:
    state[key] = int(state.get(key, 0)) + 1


@dataclass
class DailyCap:
    """Process-wide cap on paid API calls per day (protects the shared credits)."""

    limit: int = DEFAULT_DAILY_CALL_CAP
    day: date = field(default_factory=date.today)
    used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def try_spend(self, n: int) -> bool:
        with self._lock:
            if date.today() != self.day:
                self.day, self.used = date.today(), 0
            if self.used + n > self.limit:
                return False
            self.used += n
            return True


# --- input checks -------------------------------------------------------------------


def parse_sentences(text: str) -> tuple[list[str], list[str]]:
    """One sentence per line -> (sentences, problems)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    problems = []
    if len(lines) > MAX_SENTENCES:
        problems.append(f"At most {MAX_SENTENCES} sentences per run (you entered {len(lines)}).")
    for i, ln in enumerate(lines, start=1):
        if not _TAMIL.search(ln):
            problems.append(f"Line {i}: write it in Tamil script.")
        if re.search(r"\d", ln):
            problems.append(f"Line {i}: write numbers as words (e.g. இருபத்தைந்து, not 25).")
        if len(ln) > MAX_SENTENCE_CHARS:
            problems.append(f"Line {i}: keep sentences under {MAX_SENTENCE_CHARS} characters.")
    return lines[:MAX_SENTENCES], problems


# --- diff highlighting --------------------------------------------------------------


def diff_html(reference: str, hypothesis: str) -> str:
    """Word-level diff: deleted reference words struck in red, inserted words in green."""
    ref, hyp = reference.split(), hypothesis.split()
    out: list[str] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=ref, b=hyp, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(html.escape(" ".join(ref[i1:i2])))
            continue
        if i2 > i1:
            out.append(f"<del style='color:#c62828'>{html.escape(' '.join(ref[i1:i2]))}</del>")
        if j2 > j1:
            out.append(f"<ins style='color:#1b7f3b;text-decoration:none;font-weight:600'>{html.escape(' '.join(hyp[j1:j2]))}</ins>")
    return " ".join(out)


def filter_records(records: list[dict[str, Any]], **filters: list[str] | None) -> list[dict[str, Any]]:
    """Keep records whose field is in the chosen values; empty/None filter = no filtering."""
    out = []
    for r in records:
        if all(not vals or r.get(k) in vals for k, vals in filters.items()):
            out.append(r)
    return out


# --- user jobs ----------------------------------------------------------------------


def _conditions_for(noise: NoiseBank) -> tuple[str, str]:
    """C1 vs C4; falls back to C2 when the server has no noise clips."""
    return ("C1", "C4") if noise.clips else ("C1", "C2")


def _transcribe_pair(prisma: Any, audio: bytes, name: str, f0: PrismaSettings, f2: PrismaSettings,
                     lexicon: Lexicon, pool: ThreadPoolExecutor) -> tuple[str, str, int]:
    """F0 and F2 in parallel; F3 = lexicon(F2) with no extra call. Returns (F0, F3, new calls)."""
    a = pool.submit(prisma.transcribe, audio, name, f0)
    b = pool.submit(prisma.transcribe, audio, name, f2)
    r0, r2 = a.result(), b.result()
    return r0.transcript, lexicon.apply(r2.transcript), int(not r0.cached) + int(not r2.cached)


def run_sentence_job(
    sentences: list[str],
    voice: str,
    tts_model: str,
    timbre: Any,
    prisma: Any,
    noise: NoiseBank,
    bias_words: tuple[str, ...],
    lexicon: Lexicon,
    seed: int = 42,
    workers: int = 4,
) -> dict[str, Any]:
    """Timbre -> C1 and C4 -> Prisma F0 and F3 for each sentence; returns a mini report.

    Fast and frugal: duplicate sentences are processed once, sentences and conditions run in
    parallel (the clients' shared throttle still paces paid calls), cached calls cost nothing,
    and F3 reuses the F2 call."""
    start = time.perf_counter()
    clean_cond, noisy_cond = _conditions_for(noise)
    f0 = PrismaSettings(format="verbatim")
    f2 = PrismaSettings(format="transcribe", bias_list=bias_words, bias_score=BIAS_SCORE if bias_words else None)
    unique = list(dict.fromkeys(sentences))
    new_calls = 0
    lock = threading.Lock()

    def one(i: int, text: str, tmpdir: Path, pool: ThreadPoolExecutor) -> dict[str, Any]:
        nonlocal new_calls
        tts = timbre.synthesize(text, TimbreSettings(voice=voice, model=tts_model))  # type: ignore[arg-type]
        src = tmpdir / f"s{i}.wav"
        src.write_bytes(tts.audio)
        clean = load_clean(src)
        row: dict[str, Any] = {"sentence": text, "audio": {}, "scores": {}}
        calls = int(not tts.cached)
        for cond in (clean_cond, noisy_cond):
            path = tmpdir / cond / f"s{i}.wav"
            build_condition(clean, f"user{i}", CONDITIONS[cond], path, noise, seed)
            audio = path.read_bytes()
            row["audio"][cond] = audio
            hyp0, hyp3, n = _transcribe_pair(prisma, audio, path.name, f0, f2, lexicon, pool)
            calls += n
            for setting, hyp in (("F0", hyp0), ("F3", hyp3)):
                sc = score_utterance(text, hyp)
                row[f"{cond}_{setting}"] = hyp
                row[f"{cond}_{setting}_cer"] = sc.char_edits / sc.char_ref if sc.char_ref else 0.0
                row["scores"][(cond, setting)] = sc
        with lock:
            new_calls += calls
        return row

    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=max(2, workers * 2)) as inner,             ThreadPoolExecutor(max_workers=workers) as outer:  # fmt: skip
        futures = [outer.submit(one, i, t, Path(tmp), inner) for i, t in enumerate(unique)]
        by_text = {r["sentence"]: r for r in (f.result() for f in futures)}
    rows = [by_text[t] for t in sentences]  # original order, duplicates included
    scores: dict[tuple[str, str], list] = {}
    for r in by_text.values():
        for key, sc in r.pop("scores").items():
            scores.setdefault(key, []).append(sc)
    overall = {f"{c}_{s}": corpus_cer(v) for (c, s), v in scores.items()}
    return {
        "rows": rows,
        "overall_cer": overall,
        "n": len(by_text),
        "conditions": (clean_cond, noisy_cond),
        "stats": {"elapsed_ms": round((time.perf_counter() - start) * 1000), "new_api_calls": new_calls,
                  "duplicates_skipped": len(sentences) - len(unique)},
    }


def run_voice_job(
    audio: bytes,
    filename: str,
    prisma: Any,
    noise: NoiseBank,
    reference: str = "",
    seed: int = 42,
    bias_words: tuple[str, ...] = (),
    lexicon: Lexicon | None = None,
) -> dict[str, Any]:
    """User recording -> clean (C1) and phone + light noise (C3, or C2 without noise clips)
    -> Prisma F0 and F3 (fix layer), all four calls in parallel.
    Audio stays in a temp dir that is deleted on return."""
    start = time.perf_counter()
    phone_cond = "C3" if noise.clips else "C2"
    lexicon = lexicon or Lexicon([])
    f0 = PrismaSettings(format="verbatim")
    f2 = PrismaSettings(format="transcribe", bias_list=bias_words, bias_score=BIAS_SCORE if bias_words else None)
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / (Path(filename).name or "voice.wav")
        src.write_bytes(audio)
        clean = load_clean(src)
        seconds = len(clean) / 16000
        if seconds > MAX_VOICE_SECONDS:
            raise ValueError(f"Recording is {seconds:.0f} s; please keep it under {MAX_VOICE_SECONDS} s.")
        if seconds < 0.3:
            raise ValueError("Recording is too short.")
        result: dict[str, Any] = {"seconds": round(seconds, 1), "phone_condition": phone_cond, "audio": {}}
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {}
            for cond in ("C1", phone_cond):
                path = tmpdir / cond / "voice.wav"
                build_condition(clean, f"voice-{time.time_ns()}", CONDITIONS[cond], path, noise, seed)
                data = path.read_bytes()
                result["audio"][cond] = data
                jobs[cond] = pool.submit(_transcribe_pair, prisma, data, "voice.wav", f0, f2, lexicon, pool)
            for cond, fut in jobs.items():
                hyp0, hyp3, _ = fut.result()
                result[cond], result[f"{cond}_F3"] = hyp0, hyp3
                if reference.strip():
                    for key, hyp in ((f"{cond}_cer", hyp0), (f"{cond}_F3_cer", hyp3)):
                        sc = score_utterance(reference, hyp)
                        result[key] = sc.char_edits / sc.char_ref if sc.char_ref else 0.0
        result["sample_rates"] = {c: sf.info(io.BytesIO(result["audio"][c])).samplerate for c in result["audio"]}
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
    return result

