"""Whisper small (offline) on the same condition audio, same normalisation and scoring as Prisma.

    uv sync --group whisper
    uv run python scripts/run_whisper.py --split test

Writes results/<date>_<split>_whisper/ in the same format, with model='whisper-small', setting W0.
No API calls and no credits; the first run downloads the model (~480 MB).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck import runner  # noqa: E402
from kuralcheck.cache import Cache  # noqa: E402
from kuralcheck.clients.whisper_local import WhisperLocal  # noqa: E402
from kuralcheck.config import get_settings  # noqa: E402
from kuralcheck.data import display_path, load_sentences, results_dir, utterances  # noqa: E402
from kuralcheck.errors import errors_markdown  # noqa: E402
from kuralcheck.fixlayer.lexicon import Lexicon  # noqa: E402
from kuralcheck.report.tables import summary_markdown  # noqa: E402

SETTING = "W0"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["dev", "test"], required=True)
    p.add_argument("--conditions", default="C1,C2,C3,C4")
    p.add_argument("--source", choices=["timbre", "real", "all"], default="all")
    p.add_argument("--model-size", default="small")
    p.add_argument("--workers", type=int, default=1, help="CPU threads are shared; 1 is usually fastest")
    args = p.parse_args()

    conds = [c.strip() for c in args.conditions.split(",")]
    utts = [
        u for u in utterances(load_sentences())
        if u.sentence.split == args.split and args.source in ("all", u.sentence.source)
    ]  # fmt: skip
    jobs, missing = runner.plan_jobs(utts, conds, ["F0"], ())
    print(f"Split {args.split}: {len(utts)} utterances, {len(jobs)} files to transcribe offline")
    if missing:
        print(f"  {len(missing)} (utterance, condition) pairs have no audio: run build_conditions.py")
    if not jobs:
        return 1

    cache = Cache(get_settings().cache_path)
    try:
        whisper = WhisperLocal(cache, model_size=args.model_size)
        results = runner.run_calls(
            jobs, whisper, args.workers,
            progress=lambda i, n: print(f"  {i}/{n}") if i % 25 == 0 or i == n else None,
        )  # fmt: skip
        records = runner.build_records(jobs, results, Lexicon([]), model=whisper.name)
        for r in records:
            r["setting"] = SETTING
        meta = {
            "split": args.split,
            "source": args.source,
            "conditions": conds,
            "settings": [SETTING],
            "models": {"stt": whisper.name, "runtime": "faster-whisper (CTranslate2, int8, CPU)", "language": "ta"},
        }
        summary = runner.summarize_run(records, meta)
        out = results_dir() / f"{date.today().isoformat()}_{args.split}_whisper"
        out.mkdir(parents=True, exist_ok=True)
        with (out / "raw.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "errors.md").write_text(errors_markdown(records), encoding="utf-8")
        (out / "tables.md").write_text(summary_markdown(summary), encoding="utf-8")
        print(summary_markdown(summary, headline_only=True))
        print(f"Results: {display_path(out)}/  ->  now run scripts/make_report.py")
        return 0
    except RuntimeError as exc:
        print(f"Failed: {exc}")
        return 1
    finally:
        cache.close()


if __name__ == "__main__":
    sys.exit(main())
