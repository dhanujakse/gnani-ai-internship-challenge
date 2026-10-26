"""Checks for data/sentences.csv and data/real/. Errors fail the build; warnings flag
an incomplete test set (fewer items than the plan) without failing.
"""

import csv
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import soundfile as sf

from kuralcheck.clients.timbre import TAMIL_VOICES_V25
from kuralcheck.data import (
    CATEGORIES,
    COLUMNS,
    DIALECTS,
    REAL_AUDIO_DIR,
    SENTENCES_CSV,
    SOURCES,
    SPLITS,
    load_rows,
    row_to_sentence,
)
from kuralcheck.text.normalize import normalize

CONSENT_CSV = REAL_AUDIO_DIR / "consent.csv"
CONSENT_COLUMNS = ["speaker", "consent", "date", "dialect"]
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SPEAKER_RE = re.compile(r"^S\d{2}$")  # anonymous codes only, never names
LONG_DIGITS_RE = re.compile(r"(?:\d[ -]?){8,}")  # 8+ digits: phone numbers, IDs
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
TAMIL_RE = re.compile(r"[஀-௿]")

# The plan in the project notes: (source, category or "*", split) -> target count
TARGETS: dict[tuple[str, str, str], int] = {
    ("timbre", "*", "*"): 60,
    ("timbre", "*", "dev"): 20,
    ("timbre", "*", "test"): 40,
    ("timbre", "numbers", "*"): 15,
    ("timbre", "names_places", "*"): 10,
    ("timbre", "code_mixed", "*"): 15,
    ("timbre", "everyday", "*"): 20,
    ("real", "*", "*"): 30,
    ("real", "*", "dev"): 10,
    ("real", "*", "test"): 20,
}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_audio(path: Path, where: str, report: Report) -> None:
    if not path.exists():
        report.errors.append(f"{where}: audio file missing: {path.as_posix()}")
        return
    try:
        info = sf.info(path)
    except Exception:
        report.errors.append(f"{where}: cannot read audio (use WAV): {path.name}")
        return
    seconds = info.frames / info.samplerate
    if seconds > 60:
        report.errors.append(f"{where}: audio is {seconds:.0f} s; Prisma accepts at most 60 s")
    if not 8000 <= info.samplerate <= 44100:
        report.errors.append(f"{where}: sample rate {info.samplerate} Hz; must be 8-44.1 kHz")


def load_consent(path: Path = CONSENT_CSV) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["speaker"].strip(): r for r in csv.DictReader(f)}


def validate(
    csv_path: Path = SENTENCES_CSV,
    real_dir: Path = REAL_AUDIO_DIR,
    consent_path: Path | None = None,
    check_targets: bool = True,
) -> Report:
    report = Report()
    header, rows = load_rows(csv_path)
    if header != COLUMNS:
        report.errors.append(f"header must be exactly: {','.join(COLUMNS)} (got {','.join(header)})")
        return report

    consent = load_consent(consent_path or real_dir / "consent.csv")
    seen: set[str] = set()
    for line_no, row in enumerate(rows, start=2):  # line 1 is the header
        where = f"line {line_no}"
        if any(v is None for v in row.values()) or None in row:
            report.errors.append(f"{where}: wrong number of columns (quote text that contains commas)")
            continue
        s = row_to_sentence(row)
        where = f"line {line_no} ({s.id or 'no id'})"

        if not ID_RE.match(s.id):
            report.errors.append(f"{where}: id must be lowercase letters/digits/_ (e.g. num01)")
        if s.id in seen:
            report.errors.append(f"{where}: duplicate id")
        seen.add(s.id)

        if not s.text:
            report.errors.append(f"{where}: empty text")
        elif not TAMIL_RE.search(s.text):
            report.errors.append(f"{where}: text has no Tamil script")
        if s.text != unicodedata.normalize("NFC", s.text):
            report.warnings.append(f"{where}: text is not NFC-normalised")
        if s.source not in SOURCES:
            report.errors.append(f"{where}: source must be one of {SOURCES}")
        if s.split not in SPLITS:
            report.errors.append(f"{where}: split must be one of {SPLITS}")
        if s.category not in CATEGORIES:
            report.errors.append(f"{where}: category must be one of {CATEGORIES}")
        if s.dialect not in DIALECTS:
            report.errors.append(f"{where}: dialect must be one of {DIALECTS}")

        # Personal data: no phone numbers, IDs or emails anywhere in the row.
        joined = " ".join(row.values())
        if LONG_DIGITS_RE.search(joined) or EMAIL_RE.search(joined):
            report.errors.append(f"{where}: looks like a phone number, ID or email; remove it")

        # Variants: "a=b" word swaps must swap a word that is actually in the text.
        words = set(normalize(s.text).split())
        for v in s.accepted_variants:
            if "=" in v:
                formal, _, colloquial = v.partition("=")
                if not formal.strip() or not colloquial.strip():
                    report.errors.append(f"{where}: variant '{v}' must look like formal=colloquial")
                elif normalize(formal) not in words:
                    report.errors.append(f"{where}: variant '{v}': '{formal}' is not a word in the text")

        if s.source == "timbre":
            if re.search(r"\d", s.text):
                report.errors.append(f"{where}: Timbre text must write numbers as words, not digits")
            if s.dialect != "standard":
                report.errors.append(f"{where}: Timbre rows are standard Tamil (dialect=standard)")
            if not s.voices_or_speaker:
                report.errors.append(f"{where}: list Timbre voices, e.g. Trisha|Asmita|Brinda")
            unknown = [v for v in s.voices_or_speaker if v not in TAMIL_VOICES_V25]
            if unknown:
                report.warnings.append(f"{where}: {unknown} are not timbre-v2.5 Tamil voices")
        elif s.source == "real":
            if len(s.voices_or_speaker) != 1 or not SPEAKER_RE.match(s.voices_or_speaker[0]):
                report.errors.append(f"{where}: real rows need one anonymous speaker code like S01")
            elif s.voices_or_speaker[0] not in consent:
                report.errors.append(
                    f"{where}: speaker {s.voices_or_speaker[0]} has no row in data/real/consent.csv"
                )
            _check_audio(real_dir / f"{s.id}.wav", where, report)

        for cat in (s.category, "*"):
            for split in (s.split, "*"):
                report.counts[(s.source, cat, split)] += 1

    if check_targets:
        for key, target in TARGETS.items():
            got = report.counts.get(key, 0)
            if got != target:
                source, cat, split = key
                label = f"{source}" + (f" {cat}" if cat != "*" else "") + (f" {split}" if split != "*" else "")
                report.warnings.append(f"{label}: {got} items (plan: {target})")
    return report
