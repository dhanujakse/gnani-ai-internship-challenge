"""Benchmark matrix: utterances x conditions (C1-C4) x settings (F0-F3).

F0 format=verbatim
F1 format=transcribe (ITN)
F2 F1 + bias_list from data/lexicon/bias_words.txt (bias_score 1.0)
F3 F2 + lexicon post-processing. F3 reuses F2's Prisma call, so it costs nothing extra.

Every Prisma call goes through the cache. Failed calls are recorded and excluded from
the metrics (and counted as failures); a 403 (bad key / no credits) stops the run.
"""

import subprocess
import threading
from collections import defaultdict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from kuralcheck.cache import settings_json, sha256
from kuralcheck.clients.errors import ApiAuthError
from kuralcheck.clients.prisma import PrismaSettings, TranscriptResult
from kuralcheck.data import CONDITIONS_DIR, ROOT, Utterance
from kuralcheck.fixlayer.lexicon import Lexicon
from kuralcheck.metrics import UtteranceScore, score_utterance, summarize

SETTINGS = ("F0", "F1", "F2", "F3")
SETTING_LABELS = {
    "F0": "Baseline (verbatim)",
    "F1": "ITN (format=transcribe)",
    "F2": "ITN + bias words",
    "F3": "Full fix (F2 + lexicon)",
}
BIAS_SCORE = 1.0
PRISMA_MODEL = "gnani-prisma (stt/v3)"


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, filename: str, settings: PrismaSettings) -> TranscriptResult: ...
    def is_cached(self, audio: bytes, settings: PrismaSettings) -> bool: ...


def prisma_settings(setting: str, bias_words: tuple[str, ...]) -> PrismaSettings:
    if setting == "F0":
        return PrismaSettings(format="verbatim")
    if setting == "F1":
        return PrismaSettings(format="transcribe")
    if setting in ("F2", "F3"):
        if not bias_words:
            return PrismaSettings(format="transcribe")  # same as F1 until bias words exist
        return PrismaSettings(format="transcribe", bias_list=bias_words, bias_score=BIAS_SCORE)
    raise ValueError(f"unknown setting {setting}")


@dataclass(frozen=True)
class Job:
    utt: Utterance
    condition: str
    setting: str
    audio_path: Path
    prisma: PrismaSettings


def plan_jobs(
    utts: Iterable[Utterance],
    conditions: Iterable[str],
    settings: Iterable[str],
    bias_words: tuple[str, ...],
    conditions_dir: Path = CONDITIONS_DIR,
) -> tuple[list[Job], list[tuple[str, str]]]:
    """Returns (jobs, [(utt_id, condition) with no audio])."""
    jobs: list[Job] = []
    missing: list[tuple[str, str]] = []
    settings = list(settings)
    for u in utts:
        for c in conditions:
            path = conditions_dir / c / f"{u.utt_id}.wav"
            if not path.exists():
                missing.append((u.utt_id, c))
                continue
            for s in settings:
                jobs.append(Job(u, c, s, path, prisma_settings(s, bias_words)))
    return jobs, missing


def unique_calls(jobs: Iterable[Job]) -> dict[tuple[Path, PrismaSettings], None]:
    """One Prisma call per (audio file, Prisma settings); F3 shares F2's, F2 shares F1's if no bias words."""
    return dict.fromkeys((j.audio_path, j.prisma) for j in jobs)


def count_new_calls(jobs: Iterable[Job], client: Transcriber) -> tuple[int, int]:
    """(new calls, total unique calls)."""
    calls = unique_calls(jobs)
    new = sum(1 for path, ps in calls if not client.is_cached(path.read_bytes(), ps))
    return new, len(calls)


def run_calls(
    jobs: list[Job],
    client: Transcriber,
    workers: int = 4,
    progress: Callable[[int, int], None] | None = None,
) -> dict[tuple[Path, PrismaSettings], TranscriptResult | Exception]:
    calls = list(unique_calls(jobs))
    results: dict[tuple[Path, PrismaSettings], TranscriptResult | Exception] = {}
    stop = threading.Event()

    def one(path: Path, ps: PrismaSettings) -> TranscriptResult:
        if stop.is_set():
            raise RuntimeError("skipped: run stopped after an auth/credits error")
        try:
            return client.transcribe(path.read_bytes(), path.name, ps)
        except ApiAuthError:
            stop.set()
            raise

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, p, ps): (p, ps) for p, ps in calls}
        for i, fut in enumerate(as_completed(futures), start=1):
            key = futures[fut]
            try:
                results[key] = fut.result()
            except Exception as exc:
                results[key] = exc
            if progress:
                progress(i, len(calls))
    if stop.is_set():
        raise ApiAuthError("Prisma returned 403: check GNANI_API_KEY and remaining credits", 403)
    return results


def build_records(
    jobs: list[Job],
    results: dict[tuple[Path, PrismaSettings], TranscriptResult | Exception],
    lexicon: Lexicon,
    model: str = PRISMA_MODEL,
) -> list[dict[str, Any]]:
    records = []
    for j in jobs:
        s = j.utt.sentence
        res = results[(j.audio_path, j.prisma)]
        rec: dict[str, Any] = {
            "model": model,
            "call_id": call_id(j.audio_path, j.prisma),
            "utt_id": j.utt.utt_id,
            "sentence_id": s.id,
            "source": s.source,
            "category": s.category,
            "dialect": s.dialect,
            "voice_or_speaker": j.utt.voice_or_speaker,
            "split": s.split,
            "condition": j.condition,
            "setting": j.setting,
            "reference": s.text,
            "accepted_variants": list(s.accepted_variants),
        }
        if isinstance(res, Exception):
            rec.update(error=str(res) or type(res).__name__, hypothesis_raw=None, hypothesis=None)
            records.append(rec)
            continue
        hyp, hits = lexicon.apply_with_hits(res.transcript) if j.setting == "F3" else (res.transcript, [])
        rec.update(
            error=None,
            hypothesis_raw=res.transcript,
            hypothesis=hyp,
            lexicon_hits=hits,
            latency_ms=round(res.latency_ms, 1),
            cached=res.cached,
            **score_fields(score_utterance(s.text, hyp, s.accepted_variants)),
        )
        records.append(rec)
    return records


def call_id(audio_path: Path, ps: PrismaSettings) -> str:
    """Identifies the Prisma call behind a record (F3 shares F2's id; F2 shares F1's if no bias words)."""
    return sha256(f"{audio_path.parent.name}/{audio_path.name}|{settings_json(ps.as_dict())}".encode())[:16]


def score_fields(sc: UtteranceScore) -> dict[str, Any]:
    return {
        "ref_used": sc.reference,
        "hyp_norm": sc.hypothesis,
        "char_edits": sc.char_edits,
        "char_ref": sc.char_ref,
        "word_edits": sc.word_edits,
        "word_ref": sc.word_ref,
        "num_matched": sc.num_matched,
        "num_ref": sc.num_ref,
    }


def record_score(rec: dict[str, Any]) -> UtteranceScore:
    return UtteranceScore(
        rec["ref_used"], rec["hyp_norm"], rec["char_edits"], rec["char_ref"],
        rec["word_edits"], rec["word_ref"], rec["num_matched"], rec["num_ref"],
    )  # fmt: skip


def _group(records: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[tuple(r[k] for k in keys)].append(r)
    rows = []
    for key in sorted(groups):
        recs = groups[key]
        ok = [r for r in recs if r.get("error") is None]
        row = dict(zip(keys, key, strict=True))
        row.update(summarize([record_score(r) for r in ok]))
        row["failures"] = len(recs) - len(ok)
        rows.append(row)
    return rows


def latency_stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"p50": None, "p95": None, "n": 0}
    arr = np.array(values, dtype=float)
    return {"p50": round(float(np.percentile(arr, 50)), 1), "p95": round(float(np.percentile(arr, 95)), 1), "n": len(values)}


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        return out.stdout.strip() or None
    except OSError:
        return None


def summarize_run(records: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    """summary.json: run metadata, metrics by (source, condition, setting), by category and dialect."""
    ok = [r for r in records if r.get("error") is None]
    # latency and call counts once per Prisma call (several settings can share one call)
    calls = {r["call_id"]: r for r in ok}
    by_condition = defaultdict(list)
    for r in calls.values():
        by_condition[r["condition"]].append(r["latency_ms"])
    return {
        "run": {
            **meta,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_commit": git_commit(),
            "n_records": len(records),
            "n_failures": len(records) - len(ok),
            "n_utterances": len({r["utt_id"] for r in records}),
            "prisma_calls": {
                "unique": len(calls),
                "new": sum(1 for r in calls.values() if not r["cached"]),
                "from_cache": sum(1 for r in calls.values() if r["cached"]),
            },
            "latency_ms": latency_stats([r["latency_ms"] for r in calls.values()]),
            "latency_ms_by_condition": {c: latency_stats(v) for c, v in sorted(by_condition.items())},
        },
        "overall": _group(records, ("model", "source", "condition", "setting")),
        "by_category": _group(records, ("model", "source", "category", "condition", "setting")),
        "by_dialect": _group([r for r in records if r["source"] == "real"], ("model", "dialect", "condition", "setting")),
    }
