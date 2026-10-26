"""Validate data/sentences.csv and data/real/. Exit code 1 on any error.

    uv run python scripts/validate_data.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.data import SENTENCES_CSV  # noqa: E402
from kuralcheck.validate import validate  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=SENTENCES_CSV)
    args = parser.parse_args()

    report = validate(args.csv)
    print(f"Checked {args.csv.as_posix()}")
    for source in ("timbre", "real"):
        total = report.counts.get((source, "*", "*"), 0)
        dev = report.counts.get((source, "*", "dev"), 0)
        test = report.counts.get((source, "*", "test"), 0)
        print(f"  {source:6s}: {total:3d} sentences (dev {dev}, test {test})")
    for w in report.warnings:
        print(f"  warning: {w}")
    for e in report.errors:
        print(f"  ERROR: {e}")
    print("OK" if report.ok else f"FAILED with {len(report.errors)} error(s)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
