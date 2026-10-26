"""Export the dataset: refresh DATASHEET.md statistics and write dist/kuralcheck-ta-v1.zip.

    uv run python scripts/export_dataset.py
"""

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.data import ROOT  # noqa: E402
from kuralcheck.dataset import (  # noqa: E402
    MAX_ZIP_BYTES,
    ZIP_NAME,
    build_zip,
    check_manifest,
    read_manifest,
    stats_markdown,
    update_datasheet,
)
from kuralcheck.validate import validate  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "dist" / f"{ZIP_NAME}.zip")
    args = p.parse_args()

    report = validate()
    if not report.ok:
        print("Data validation failed; fix these first (scripts/validate_data.py):")
        for e in report.errors:
            print(f"  ERROR: {e}")
        return 1
    manifest = read_manifest()
    if not manifest:
        print("No condition audio yet: run synthesize_set.py and build_conditions.py first.")
        return 1
    problems = check_manifest(manifest)
    if problems:
        for prob in problems[:20]:
            print(f"  ERROR: {prob}")
        return 1

    stats = stats_markdown(manifest)
    update_datasheet(stats)
    print("Updated DATASHEET.md statistics:\n" + stats)

    out = build_zip(args.out, manifest)
    size = out.stat().st_size
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        n = len(z.namelist())
    print(f"Wrote {out.relative_to(ROOT).as_posix()}: {n} files, {size / 1e6:.1f} MB")
    if bad:
        print(f"  ERROR: corrupt entry {bad}")
        return 1
    if size > MAX_ZIP_BYTES:
        print(f"  ERROR: zip is over {MAX_ZIP_BYTES / 1e6:.0f} MB")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
