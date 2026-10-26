import csv
import hashlib
import zipfile
from pathlib import Path

from kuralcheck.dataset import build_zip, check_manifest, stats_markdown, update_datasheet
from tests.conftest import make_wav

FIELDS = ["utt_id", "condition", "path", "sample_rate", "duration_s", "snr_db_target",
          "snr_db_actual", "noise_file", "noise_offset_s", "seed", "sha256"]  # fmt: skip


def fake_manifest(tmp_path: Path) -> tuple[list[dict], Path]:
    rows = []
    for cond, sr, snr in (("C1", 16000, ""), ("C4", 8000, "5.0")):
        p = tmp_path / cond / "num01__Trisha.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(make_wav(2.0, sr))
        rows.append({"utt_id": "num01__Trisha", "condition": cond, "path": p.as_posix(), "sample_rate": str(sr),
                     "duration_s": "2.0", "snr_db_target": snr, "snr_db_actual": snr,
                     "noise_file": "fan.wav" if snr else "", "noise_offset_s": "", "seed": "42",
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})  # fmt: skip
    mpath = tmp_path / "manifest.csv"
    with mpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows, mpath


def test_stats_from_data(tmp_path) -> None:
    rows, _ = fake_manifest(tmp_path)
    md = stats_markdown(rows)
    assert "60 sentences (20 dev / 40 test)" in md
    assert "1 utterances with audio" in md
    assert "C4 measured SNR:** 5.00–5.00 dB (n=1)" in md
    assert "179 planned utterances have no audio yet" in md


def test_check_manifest_detects_changes(tmp_path) -> None:
    rows, _ = fake_manifest(tmp_path)
    assert check_manifest(rows) == []
    Path(rows[0]["path"]).write_bytes(make_wav(1.0))
    assert any("changed" in p for p in check_manifest(rows))


def test_zip_contents_and_determinism(tmp_path) -> None:
    rows, mpath = fake_manifest(tmp_path)
    a = build_zip(tmp_path / "a.zip", rows, mpath)
    b = build_zip(tmp_path / "b.zip", rows, mpath)
    assert a.read_bytes() == b.read_bytes()  # same input -> identical zip
    with zipfile.ZipFile(a) as z:
        names = set(z.namelist())
        assert z.testzip() is None
        licence = z.read("kuralcheck-ta-v1/LICENSE.txt").decode()
    assert {
        "kuralcheck-ta-v1/README.md",
        "kuralcheck-ta-v1/LICENSE.txt",
        "kuralcheck-ta-v1/sentences.csv",
        "kuralcheck-ta-v1/conditions_manifest.csv",
        "kuralcheck-ta-v1/speakers.csv",
        "kuralcheck-ta-v1/NOISE_NOTICE.txt",
        "kuralcheck-ta-v1/audio/C1/num01__Trisha.wav",
        "kuralcheck-ta-v1/audio/C4/num01__Trisha.wav",
    } <= names
    assert "Attribution 4.0 International" in licence


def test_update_datasheet_keeps_handwritten_parts(tmp_path) -> None:
    p = tmp_path / "DS.md"
    p.write_text("# T\n\nintro\n<!-- stats:start -->\nold\n<!-- stats:end -->\n\n## Consent\nkept\n", encoding="utf-8")
    update_datasheet("- new stats", p)
    text = p.read_text(encoding="utf-8")
    assert "- new stats" in text and "old" not in text and "## Consent\nkept" in text
