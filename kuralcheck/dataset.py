"""Dataset export: datasheet statistics and a deterministic zip of the condition audio.

The zip contains only what the datasheet lists: sentences.csv, the conditions manifest,
condition audio, anonymous speaker codes with dialect, the noise NOTICE and CC BY 4.0.
"""

import csv
import hashlib
import io
import zipfile
from collections import Counter
from pathlib import Path

from kuralcheck.data import DATA_DIR, NOISE_DIR, ROOT, SENTENCES_CSV, load_sentences, utterances
from kuralcheck.validate import load_consent

MANIFEST = DATA_DIR / "conditions_manifest.csv"
CC_BY = ROOT / "assets" / "licenses" / "CC-BY-4.0.txt"
DATASHEET = ROOT / "DATASHEET.md"
ZIP_NAME = "kuralcheck-ta-v1"
MAX_ZIP_BYTES = 200 * 1024 * 1024
FIXED_TIME = (2026, 11, 1, 0, 0, 0)  # deterministic zip entries
STATS_START, STATS_END = "<!-- stats:start -->", "<!-- stats:end -->"


def read_manifest(path: Path = MANIFEST) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def stats_markdown(manifest: list[dict[str, str]], sentences_csv: Path = SENTENCES_CSV) -> str:
    sents = load_sentences(sentences_csv)
    utts = utterances(sents)
    by_utt = {u.utt_id: u for u in utts}
    in_zip = {r["utt_id"] for r in manifest}
    lines = []
    for source, label in (("timbre", "Scripted (Timbre)"), ("real", "Real recordings")):
        ss = [s for s in sents if s.source == source]
        us = [u for u in utts if u.sentence.source == source and u.utt_id in in_zip]
        if not ss:
            continue
        split = Counter(s.split for s in ss)
        cats = Counter(s.category for s in ss)
        voices = sorted({u.voice_or_speaker for u in us}) or sorted({v for s in ss for v in s.voices_or_speaker})
        lines.append(
            f"- **{label}:** {len(ss)} sentences ({split.get('dev', 0)} dev / {split.get('test', 0)} test), "
            f"{len(us)} utterances with audio; categories: "
            + ", ".join(f"{c} {n}" for c, n in sorted(cats.items()))
            + (f"; voices: {', '.join(voices)}" if source == "timbre" else f"; speakers: {len(voices)}")
        )
        if source == "real":
            dialects = Counter(s.dialect for s in ss)
            lines.append("  - dialects: " + ", ".join(f"{d} {n}" for d, n in sorted(dialects.items())))
    c1 = [r for r in manifest if r["condition"] == "C1"]
    hours = sum(float(r["duration_s"]) for r in c1) / 3600
    lines.append(f"- **Audio:** {len(manifest)} files across {len({r['condition'] for r in manifest})} conditions; "
                 f"{hours * 60:.1f} minutes of speech per condition")  # fmt: skip
    for cond in ("C3", "C4"):
        snrs = [float(r["snr_db_actual"]) for r in manifest if r["condition"] == cond and r["snr_db_actual"]]
        if snrs:
            lines.append(f"- **{cond} measured SNR:** {min(snrs):.2f}–{max(snrs):.2f} dB (n={len(snrs)})")
    noise = sorted({r["noise_file"] for r in manifest if r.get("noise_file")})
    if noise:
        lines.append(f"- **Noise clips used:** {', '.join(noise)}")
    missing = [u for u in by_utt if u not in in_zip]
    if missing:
        lines.append(f"- {len(missing)} planned utterances have no audio yet and are not in the zip.")
    return "\n".join(lines)


def update_datasheet(stats: str, path: Path = DATASHEET) -> None:
    text = path.read_text(encoding="utf-8")
    head, rest = text.split(STATS_START, 1)
    _, tail = rest.split(STATS_END, 1)
    path.write_text(f"{head}{STATS_START}\n{stats}\n{STATS_END}{tail}", encoding="utf-8")


def speakers_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["speaker", "dialect"])
    for code, row in sorted(load_consent().items()):
        w.writerow([code, (row.get("dialect") or "").strip()])
    return buf.getvalue()


def check_manifest(manifest: list[dict[str, str]]) -> list[str]:
    """Every listed file exists and matches its sha256."""
    problems = []
    for r in manifest:
        p = ROOT / r["path"]
        if not p.exists():
            problems.append(f"missing {r['path']}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
            problems.append(f"changed since manifest: {r['path']} (re-run build_conditions.py)")
    return problems


def _add(z: zipfile.ZipFile, name: str, data: bytes, compress: bool = True) -> None:
    info = zipfile.ZipInfo(f"{ZIP_NAME}/{name}", date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    z.writestr(info, data)


def build_zip(out: Path, manifest: list[dict[str, str]], manifest_path: Path = MANIFEST) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as z:
        _add(z, "README.md", DATASHEET.read_bytes())
        _add(z, "LICENSE.txt", CC_BY.read_bytes())
        _add(z, "sentences.csv", SENTENCES_CSV.read_bytes())
        _add(z, "conditions_manifest.csv", manifest_path.read_bytes())
        _add(z, "speakers.csv", speakers_csv().encode("utf-8"))
        notice = NOISE_DIR / "NOTICE"
        if notice.exists():
            _add(z, "NOISE_NOTICE.txt", notice.read_bytes())
        for r in sorted(manifest, key=lambda r: (r["condition"], r["utt_id"])):
            _add(z, f"audio/{r['condition']}/{r['utt_id']}.wav", (ROOT / r["path"]).read_bytes())
    return out
