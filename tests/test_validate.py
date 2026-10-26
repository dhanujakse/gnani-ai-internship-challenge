from pathlib import Path

import pytest

from kuralcheck.data import COLUMNS, load_sentences, utterances
from kuralcheck.validate import validate
from tests.conftest import make_wav

HEADER = ",".join(COLUMNS)
GOOD = [
    'num01,"ஒரு கிலோ தக்காளி இருபத்தைந்து ரூபாய்.",இருபத்தைந்து=25,numbers,standard,timbre,Trisha|Asmita,dev',
    "plc01,நாங்கள் மதுரைக்கு போகிறோம்.,,names_places,standard,timbre,Trisha,test",
    "real01,அவங்க நாளைக்கு வருவாங்க,அவர்கள் நாளைக்கு வருவாங்க,colloquial,madurai,real,S01,test",
]


def write(tmp_path: Path, rows: list[str], header: str = HEADER, consent: bool = True) -> Path:
    real = tmp_path / "real"
    real.mkdir(exist_ok=True)
    (real / "real01.wav").write_bytes(make_wav(1.0))
    if consent:
        (real / "consent.csv").write_text(
            "speaker,consent,date,dialect\nS01,yes,2026-10-27,madurai\n", encoding="utf-8"
        )
    path = tmp_path / "sentences.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def run(tmp_path: Path, rows: list[str], **kw):
    path = write(tmp_path, rows, **kw)
    return validate(path, real_dir=tmp_path / "real", check_targets=False)


def test_good_rows_pass(tmp_path) -> None:
    report = run(tmp_path, GOOD)
    assert report.ok, report.errors


def test_repo_sentences_pass() -> None:
    report = validate()
    assert report.ok, report.errors


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (GOOD[0].replace("num01", "plc01"), "duplicate id"),
        (GOOD[0].replace(",dev", ",train"), "split"),
        (GOOD[0].replace("numbers", "misc"), "category"),
        (GOOD[0].replace("இருபத்தைந்து ரூபாய்", "25 ரூபாய்"), "numbers as words"),
        (GOOD[0].replace("இருபத்தைந்து=25", "முப்பது=30"), "not a word in the text"),
        (GOOD[0].replace("இருபத்தைந்து=25", "இருபத்தைந்து="), "formal=colloquial"),
        (GOOD[1].replace("standard", "madurai"), "standard Tamil"),
        (GOOD[1].replace("plc01", "Plc 1"), "id must be"),
        (GOOD[1].replace("நாங்கள் மதுரைக்கு போகிறோம்.", "call 98400 12345"), "phone number"),
        (GOOD[1].replace("நாங்கள் மதுரைக்கு போகிறோம்.", "hello there"), "no Tamil"),
        (GOOD[2].replace("S01", "Karthik"), "anonymous speaker code"),
        (GOOD[2].replace("S01", "S02"), "consent.csv"),
        (GOOD[2].replace("real01", "real02"), "audio file missing"),
    ],
)
def test_broken_row_fails_clearly(tmp_path, row: str, message: str) -> None:
    rows = [r for r in GOOD if r.split(",")[0] != row.split(",")[0]] + [row]
    if message == "duplicate id":
        rows = GOOD + [row]
    report = run(tmp_path, rows)
    assert not report.ok
    assert any(message in e for e in report.errors), report.errors


def test_wrong_header_fails(tmp_path) -> None:
    report = run(tmp_path, GOOD, header="id,text,category")
    assert any("header" in e for e in report.errors)


def test_unquoted_comma_fails(tmp_path) -> None:
    report = run(tmp_path, ["day01,சரி, போலாம்,,everyday,standard,timbre,Trisha,dev"])
    assert any("columns" in e for e in report.errors)


def test_real_audio_over_60s_fails(tmp_path) -> None:
    path = write(tmp_path, GOOD)
    (tmp_path / "real" / "real01.wav").write_bytes(make_wav(61))
    report = validate(path, real_dir=tmp_path / "real", check_targets=False)
    assert any("60 s" in e for e in report.errors)


def test_targets_reported_as_warnings(tmp_path) -> None:
    path = write(tmp_path, GOOD)
    report = validate(path, real_dir=tmp_path / "real", check_targets=True)
    assert report.ok
    assert any("plan: 60" in w for w in report.warnings)


def test_utterances_expand_voices(tmp_path) -> None:
    path = write(tmp_path, GOOD)
    utts = utterances(load_sentences(path), timbre_dir=tmp_path / "t", real_dir=tmp_path / "real")
    assert [u.utt_id for u in utts] == ["num01__Trisha", "num01__Asmita", "plc01__Trisha", "real01"]
    assert utts[-1].source_audio == tmp_path / "real" / "real01.wav"
