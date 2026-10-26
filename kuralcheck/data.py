"""Loading data/sentences.csv and expanding it into utterances (one audio file each).

A Timbre sentence is spoken by several voices, so it becomes several utterances
("num01__Trisha", "num01__Asmita", ...). A real recording is one utterance ("real01").
"""

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SENTENCES_CSV = DATA_DIR / "sentences.csv"
TIMBRE_AUDIO_DIR = DATA_DIR / "audio" / "timbre"
REAL_AUDIO_DIR = DATA_DIR / "real"
CONDITIONS_DIR = DATA_DIR / "audio" / "conditions"
NOISE_DIR = DATA_DIR / "noise"
LEXICON_DIR = DATA_DIR / "lexicon"
RESULTS_DIR = ROOT / "results"

COLUMNS = ["id", "text", "accepted_variants", "category", "dialect", "source", "voice_or_speaker", "split"]
SOURCES = ("timbre", "real")
SPLITS = ("dev", "test")
CATEGORIES = ("numbers", "names_places", "code_mixed", "everyday", "colloquial", "dialect", "slang")
DIALECTS = ("standard", "chennai", "madurai", "kongu", "tirunelveli", "thanjavur", "jaffna", "other")


@dataclass(frozen=True)
class Sentence:
    id: str
    text: str
    accepted_variants: tuple[str, ...]
    category: str
    dialect: str
    source: str
    voices_or_speaker: tuple[str, ...]  # Timbre voices, or one anonymous speaker code (S01)
    split: str


@dataclass(frozen=True)
class Utterance:
    utt_id: str
    sentence: Sentence
    voice_or_speaker: str
    source_audio: Path  # clean audio before conditions


def split_list(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split("|") if v.strip())


def load_rows(path: Path = SENTENCES_CSV) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def row_to_sentence(row: dict[str, str]) -> Sentence:
    return Sentence(
        id=row["id"].strip(),
        text=row["text"].strip(),
        accepted_variants=split_list(row.get("accepted_variants") or ""),
        category=row["category"].strip(),
        dialect=row["dialect"].strip(),
        source=row["source"].strip(),
        voices_or_speaker=split_list(row["voice_or_speaker"]),
        split=row["split"].strip(),
    )


def load_sentences(path: Path = SENTENCES_CSV) -> list[Sentence]:
    _, rows = load_rows(path)
    return [row_to_sentence(r) for r in rows]


def utterances(
    sentences: list[Sentence],
    timbre_dir: Path = TIMBRE_AUDIO_DIR,
    real_dir: Path = REAL_AUDIO_DIR,
) -> list[Utterance]:
    out: list[Utterance] = []
    for s in sentences:
        if s.source == "timbre":
            for voice in s.voices_or_speaker:
                utt_id = f"{s.id}__{voice}"
                out.append(Utterance(utt_id, s, voice, timbre_dir / f"{utt_id}.wav"))
        else:
            out.append(Utterance(s.id, s, s.voices_or_speaker[0], real_dir / f"{s.id}.wav"))
    return out
