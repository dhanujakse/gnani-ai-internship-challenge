"""Build C1-C4 audio for every utterance that has clean audio.

    uv run python scripts/build_conditions.py --seed 42

Writes data/audio/conditions/<C>/<utt_id>.wav and data/conditions_manifest.csv
(one row per file with target and measured SNR, noise clip, offset and sha256).
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.audio.conditions import CONDITIONS, NoiseBank, build_all_conditions  # noqa: E402
from kuralcheck.data import CONDITIONS_DIR, DATA_DIR, NOISE_DIR, ROOT, load_sentences, utterances  # noqa: E402

MANIFEST = DATA_DIR / "conditions_manifest.csv"
FIELDS = [
    "utt_id", "condition", "path", "sample_rate", "duration_s", "snr_db_target",
    "snr_db_actual", "noise_file", "noise_offset_s", "seed", "sha256",
]  # fmt: skip


def read_manifest(path: Path = MANIFEST) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {(r["utt_id"], r["condition"]): r for r in csv.DictReader(f)}


def write_manifest(rows: dict[tuple[str, str], dict], path: Path = MANIFEST) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n")
        w.writeheader()
        for key in sorted(rows):
            w.writerow({k: rows[key].get(k) for k in FIELDS})


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--split", choices=["dev", "test", "all"], default="all")
    p.add_argument("--source", choices=["timbre", "real", "all"], default="all")
    p.add_argument("--conditions", default="C1,C2,C3,C4")
    args = p.parse_args()

    conds = tuple(c.strip() for c in args.conditions.split(","))
    unknown = [c for c in conds if c not in CONDITIONS]
    if unknown:
        print(f"Unknown condition(s): {unknown}")
        return 1

    utts = [
        u for u in utterances(load_sentences())
        if args.split in ("all", u.sentence.split) and args.source in ("all", u.sentence.source)
    ]  # fmt: skip
    present = [u for u in utts if u.source_audio.exists()]
    missing = len(utts) - len(present)
    print(f"{len(present)} utterances with audio ({missing} without audio skipped)")
    if missing:
        print("  Timbre audio: run scripts/synthesize_set.py; real audio: see data/real/README.md")
    if not present:
        return 1

    noise = NoiseBank.load(NOISE_DIR) if any(CONDITIONS[c].snr_db is not None for c in conds) else NoiseBank([])
    if any(CONDITIONS[c].snr_db is not None for c in conds):
        print(f"Noise clips: {[name for name, _ in noise.clips] or 'NONE - add WAVs to data/noise/'}")
        if not noise.clips:
            return 1

    manifest = read_manifest()
    for i, u in enumerate(present, start=1):
        rows = build_all_conditions(u.source_audio, u.utt_id, CONDITIONS_DIR, noise, args.seed, conds)
        for cond, row in rows.items():
            row["path"] = Path(row["path"]).resolve().relative_to(ROOT).as_posix()
            manifest[(u.utt_id, cond)] = row
        if i % 20 == 0 or i == len(present):
            print(f"  {i}/{len(present)} done")
    write_manifest(manifest)

    for c in conds:
        snrs = [float(r["snr_db_actual"]) for (_, cc), r in manifest.items() if cc == c and r.get("snr_db_actual") not in (None, "")]
        line = f"  {c}: {sum(1 for (_, cc) in manifest if cc == c)} files"
        if snrs:
            line += f", measured SNR {min(snrs):.2f}-{max(snrs):.2f} dB"
        print(line)
    print(f"Manifest: {MANIFEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
