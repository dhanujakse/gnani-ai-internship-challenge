"""Run Prisma over utterances x conditions x settings and write results/<date>_<split>/.

    uv run python scripts/run_benchmark.py --split dev --dry-run          # count new calls only
    uv run python scripts/run_benchmark.py --split dev                    # tune the fix layer on this
    uv run python scripts/run_benchmark.py --split test --settings F0,F1,F2,F3

Outputs: raw.jsonl (one line per record), summary.json (metrics with 95% CI and n),
errors.md (worst utterances and frequent substitutions) and tables.md.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck import runner  # noqa: E402
from kuralcheck.budget import confirm_calls  # noqa: E402
from kuralcheck.cache import Cache  # noqa: E402
from kuralcheck.clients.errors import ApiAuthError  # noqa: E402
from kuralcheck.clients.prisma import PrismaClient  # noqa: E402
from kuralcheck.config import get_settings  # noqa: E402
from kuralcheck.data import display_path, load_sentences, results_dir, utterances  # noqa: E402
from kuralcheck.errors import errors_markdown  # noqa: E402
from kuralcheck.fixlayer.bias import BIAS_WORDS_TXT, file_sha, load_bias_words  # noqa: E402
from kuralcheck.fixlayer.lexicon import VARIANTS_CSV, load_lexicon  # noqa: E402
from kuralcheck.report.scorecard import make_scorecard  # noqa: E402
from kuralcheck.report.tables import summary_markdown  # noqa: E402


def write_results(out_dir: Path, records: list[dict], summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "raw.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "errors.md").write_text(errors_markdown(records), encoding="utf-8")
    (out_dir / "tables.md").write_text(summary_markdown(summary), encoding="utf-8")
    make_scorecard(out_dir / "summary.json")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["dev", "test"], required=True)
    p.add_argument("--settings", default="F0,F1,F2,F3")
    p.add_argument("--conditions", default="C1,C2,C3,C4")
    p.add_argument("--source", choices=["timbre", "real", "all"], default="all")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="skip the > 100 calls confirmation")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--tag", default="", help="suffix for the results folder name")
    args = p.parse_args()

    settings_list = [s.strip() for s in args.settings.split(",")]
    conds = [c.strip() for c in args.conditions.split(",")]
    if bad := [s for s in settings_list if s not in runner.SETTINGS]:
        print(f"Unknown settings: {bad}")
        return 1

    cfg = get_settings()
    bias = load_bias_words()
    lexicon = load_lexicon()
    utts = [
        u for u in utterances(load_sentences())
        if u.sentence.split == args.split and args.source in ("all", u.sentence.source)
    ]  # fmt: skip
    jobs, missing = runner.plan_jobs(utts, conds, settings_list, bias)
    print(f"Split {args.split}: {len(utts)} utterances, {len(jobs)} records planned")
    print(f"  bias words: {len(bias)}, lexicon rules: {len(lexicon.rules)}")
    if missing:
        print(f"  {len(missing)} (utterance, condition) pairs have no audio yet: run build_conditions.py")
    if not jobs:
        return 1
    if args.split == "test":
        print("  Reminder: tune bias_words.txt and variants.csv on dev only; test is for reporting.")

    cache = Cache(cfg.cache_path)
    try:
        if args.dry_run and not cfg.gnani_api_key.get_secret_value():
            print(f"Planned Prisma calls: {len(runner.unique_calls(jobs))} unique (no key, cache not checked)")
            return 0
        client = PrismaClient.from_settings(cfg, cache)
        new, unique = runner.count_new_calls(jobs, client)
        print(f"  unique Prisma calls: {unique} ({unique - new} cached)")
        if args.dry_run:
            print(f"Planned new Prisma calls: {new} (dry run, nothing called)")
            return 0
        if not confirm_calls(new, "Prisma", yes=args.yes):
            return 1

        results = runner.run_calls(
            jobs, client, args.workers,
            progress=lambda i, n: print(f"  {i}/{n}") if i % 25 == 0 or i == n else None,
        )  # fmt: skip
        records = runner.build_records(jobs, results, lexicon)
        meta = {
            "split": args.split,
            "source": args.source,
            "conditions": conds,
            "settings": settings_list,
            "models": {"stt": runner.PRISMA_MODEL, "stt_version": "Prisma v2.5", "tts": cfg.tts_model},
            "bias_words": {"n": len(bias), "sha": file_sha(BIAS_WORDS_TXT)},
            "lexicon": {"n_rules": len(lexicon.rules), "sha": file_sha(VARIANTS_CSV)},
        }
        summary = runner.summarize_run(records, meta)
        name = f"{date.today().isoformat()}_{args.split}" + (f"_{args.tag}" if args.tag else "")
        out = results_dir() / name
        write_results(out, records, summary)

        calls = summary["run"]["prisma_calls"]
        print(f"Done: {calls['new']} new Prisma calls, {calls['from_cache']} from cache, "
              f"{summary['run']['n_failures']} failed records")  # fmt: skip
        print(summary_markdown(summary, headline_only=True))
        print(f"Results: {display_path(out)}/")
        return 0
    except ApiAuthError as exc:
        print(f"Stopped: {exc}")
        return 1
    finally:
        cache.close()


if __name__ == "__main__":
    sys.exit(main())
