import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from streamlit.testing.v1 import AppTest

from kuralcheck import runner
from kuralcheck.audio.conditions import NoiseBank
from kuralcheck.clients.prisma import TranscriptResult
from kuralcheck.clients.timbre import SynthesisResult
from kuralcheck.data import ROOT
from kuralcheck.fixlayer.lexicon import Lexicon, Rule
from kuralcheck.webapp import (
    DailyCap,
    diff_html,
    filter_records,
    parse_sentences,
    run_sentence_job,
    run_voice_job,
    session_allows,
    session_count,
)
from tests.conftest import make_wav

APP = ROOT / "app"


def speech_wav(seconds: float = 1.0, sr: int = 16000) -> bytes:
    import io

    t = np.arange(int(seconds * sr)) / sr
    buf = io.BytesIO()
    sf.write(buf, (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class FakeTimbre:
    def synthesize(self, text, settings):
        return SynthesisResult(speech_wav(), 10.0, cached=False)


class FakePrisma:
    def __init__(self):
        self.calls = []

    def transcribe(self, audio, filename, settings):
        self.calls.append(settings.format)
        return TranscriptResult("அவங்க வந்தாங்கோ" if settings.format == "transcribe" else "அவங்க வந்தாங்க", 5.0, False)


def noise_bank(tmp_path: Path) -> NoiseBank:
    d = tmp_path / "noise"
    d.mkdir()
    sf.write(d / "n.wav", (0.1 * np.random.default_rng(0).standard_normal(32000)).astype(np.float32), 16000)
    return NoiseBank.load(d)


# --- helpers


def test_parse_sentences_rules() -> None:
    ok, problems = parse_sentences("சரி போலாம்\n\nநாளைக்கு வா\n")
    assert ok == ["சரி போலாம்", "நாளைக்கு வா"] and problems == []
    _, problems = parse_sentences("10 ரூபாய்\nhello")
    assert any("numbers as words" in p for p in problems) and any("Tamil script" in p for p in problems)
    lines, problems = parse_sentences("\n".join(["சரி"] * 12))
    assert len(lines) == 10 and any("At most 10" in p for p in problems)


def test_diff_html_marks_and_escapes() -> None:
    out = diff_html("அவர்கள் வந்தாங்க", "அவங்க வந்தாங்க <script>")
    assert "<del" in out and "அவர்கள்" in out and "<ins" in out
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_limits() -> None:
    state: dict = {}
    for _ in range(3):
        assert session_allows(state, "runs", 3)
        session_count(state, "runs")
    assert not session_allows(state, "runs", 3)
    cap = DailyCap(limit=10)
    assert cap.try_spend(6) and not cap.try_spend(5) and cap.try_spend(4)


def test_filter_records() -> None:
    recs = [{"source": "real", "condition": "C1"}, {"source": "timbre", "condition": "C4"}]
    assert filter_records(recs, source=["real"], condition=None) == recs[:1]
    assert filter_records(recs, source=[], condition=[]) == recs


# --- user jobs (fake APIs, real audio processing)


def test_sentence_job(tmp_path) -> None:
    prisma = FakePrisma()
    lex = Lexicon([Rule("வந்தாங்கோ", "வந்தாங்க", "dialect")])
    report = run_sentence_job(["அவங்க வந்தாங்க"], "Trisha", "timbre-v2.5", FakeTimbre(), prisma,
                              noise_bank(tmp_path), ("அவங்க",), lex)  # fmt: skip
    assert report["conditions"] == ("C1", "C4") and report["n"] == 1
    row = report["rows"][0]
    assert row["C4_F3"] == "அவங்க வந்தாங்க" and row["C4_F3_cer"] == 0.0
    assert report["overall_cer"]["C1_F0"] == 0.0
    assert row["audio"]["C4"][:4] == b"RIFF"
    assert len(prisma.calls) == 4


def test_sentence_job_without_noise_uses_c2(tmp_path) -> None:
    report = run_sentence_job(["சரி"], "Trisha", "timbre-v2.5", FakeTimbre(), FakePrisma(), NoiseBank([]), (), Lexicon([]))
    assert report["conditions"] == ("C1", "C2")


def test_voice_job_scores_and_leaves_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("TEMP", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    result = run_voice_job(speech_wav(2.0, 44100), "rec.wav", FakePrisma(), noise_bank(tmp_path), "அவங்க வந்தாங்க")
    assert result["phone_condition"] == "C3"
    assert result["C1_cer"] == 0.0 and result["sample_rates"] == {"C1": 16000, "C3": 8000}
    assert list((tmp_path / "tmp").iterdir()) == []  # temp audio deleted


def test_voice_job_rejects_long_and_short(tmp_path) -> None:
    with pytest.raises(ValueError, match="under 30"):
        run_voice_job(speech_wav(31), "a.wav", FakePrisma(), NoiseBank([]))
    with pytest.raises(ValueError, match="too short"):
        run_voice_job(speech_wav(0.1), "a.wav", FakePrisma(), NoiseBank([]))


# --- pages render headless


@pytest.fixture
def no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GNANI_API_KEY", "")
    monkeypatch.setenv("KURALCHECK_RESULTS_DIR", str(tmp_path / "results"))
    (tmp_path / "results").mkdir()
    return tmp_path / "results"


def _run(page: str) -> AppTest:
    at = AppTest.from_file(str(APP / page), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    return at


def test_home_without_results(no_key) -> None:
    at = _run("Home.py")
    assert any("No benchmark results yet" in i.value for i in at.info)


def test_home_with_results(no_key, tmp_path) -> None:
    from tests.test_report import whisper_from  # noqa: F401
    from tests.test_runner import FakePrisma as RunnerFake, sentences
    from kuralcheck.data import utterances

    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    for i, u in enumerate(utts):
        for c in ("C1", "C4"):
            p = tmp_path / "cond" / c / f"{u.utt_id}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(make_wav(0.2 + 0.01 * i + (0.05 if c == "C4" else 0)))
    jobs, _ = runner.plan_jobs(utts, ["C1", "C4"], runner.SETTINGS, (), tmp_path / "cond")
    records = runner.build_records(jobs, runner.run_calls(jobs, RunnerFake()), Lexicon([]))
    summary = runner.summarize_run(records, {"split": "test", "settings": list(runner.SETTINGS)})
    out = no_key / "2026-10-31_test"
    out.mkdir()
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    (out / "raw.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    at = _run("Home.py")
    assert any("Character error rate by condition" in s.value for s in at.subheader)
    assert any("Example errors" in s.value for s in at.subheader)


@pytest.mark.parametrize("page", ["pages/1_Test_your_sentences.py", "pages/2_Try_your_voice.py"])
def test_paid_pages_without_key_are_safe(no_key, page) -> None:
    at = _run(page)
    assert any("not configured" in i.value for i in at.info)


def test_download_page(no_key) -> None:
    at = _run("pages/3_Download.py")
    assert any("CC BY 4.0" in m.value for m in at.markdown)
