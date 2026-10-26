"""Regenerate tables.md, scorecard.png/.json and the README results section from results/ only.

    uv run python scripts/make_report.py                      # latest test-split run (+ latest Whisper test run)
    uv run python scripts/make_report.py --run results/2026-10-31_test --no-readme
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.data import ROOT  # noqa: E402
from kuralcheck.report.runs import Run, latest  # noqa: E402
from kuralcheck.report.scorecard import make_scorecard  # noqa: E402
from kuralcheck.report.tables import (  # noqa: E402
    comparison_markdown,
    readme_results_block,
    replace_readme_block,
    summary_markdown,
)

README = ROOT / "README.md"


def load(path: Path | None, split: str, whisper: bool) -> Run | None:
    if path is None:
        return latest(split, whisper=whisper)
    import json

    return Run(path, json.loads((path / "summary.json").read_text(encoding="utf-8")))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, help="Prisma run folder (default: latest for --split)")
    p.add_argument("--whisper", type=Path, help="Whisper run folder (default: latest for --split)")
    p.add_argument("--split", choices=["dev", "test"], default="test")
    p.add_argument("--no-readme", action="store_true", help="do not touch README.md")
    args = p.parse_args()

    prisma = load(args.run, args.split, whisper=False)
    if prisma is None:
        print(f"No Prisma results for split={args.split} in results/. Run scripts/run_benchmark.py first.")
        return 1
    whisper = load(args.whisper, prisma.split or args.split, whisper=True)

    tables = summary_markdown(prisma.summary)
    if whisper:
        for source in ("real", "timbre"):
            if any(r["source"] == source for r in whisper.summary["overall"]):
                tables += f"\n## Open-model comparison · {source} · CER %\n\n"
                tables += comparison_markdown(prisma.summary, whisper.summary, source) + "\n"
    (prisma.path / "tables.md").write_text(tables, encoding="utf-8")
    make_scorecard(prisma.path / "summary.json", whisper_summary=whisper.path / "summary.json" if whisper else None)
    print(f"Wrote {prisma.path.relative_to(ROOT).as_posix()}/tables.md, scorecard.png, scorecard.json"
          + (f" (with {whisper.name})" if whisper else ""))  # fmt: skip

    if not args.no_readme:
        if prisma.split != "test":
            print("README not updated: headline numbers come from the test split only.")
        else:
            block = readme_results_block(prisma.name, prisma.summary, whisper.summary if whisper else None)
            README.write_text(replace_readme_block(README.read_text(encoding="utf-8"), block), encoding="utf-8")
            print("Updated README.md results section")
    return 0


if __name__ == "__main__":
    sys.exit(main())
