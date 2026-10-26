import json
from pathlib import Path

import pytest

from kuralcheck import runner
from kuralcheck.clients.errors import ApiAuthError
from kuralcheck.clients.prisma import PrismaClient, PrismaSettings, TranscriptResult
from kuralcheck.data import Sentence, utterances
from kuralcheck.errors import errors_markdown, word_substitutions
from kuralcheck.fixlayer.lexicon import Lexicon, Rule
from kuralcheck.report.tables import summary_markdown
from tests.conftest import make_wav

STT = "/stt/v3"


def sentences() -> list[Sentence]:
    return [
        Sentence("num01", "இருபத்தைந்து ரூபாய்", ("இருபத்தைந்து=25",), "numbers", "standard", "timbre", ("Trisha", "Asmita"), "dev"),
        Sentence("real01", "அவங்க நாளைக்கு வருவாங்க", (), "colloquial", "madurai", "real", ("S01",), "dev"),
    ]  # fmt: skip


@pytest.fixture
def setup(tmp_path: Path):
    cond_dir = tmp_path / "conditions"
    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    for i, u in enumerate(utts):
        for c in ("C1", "C4"):
            p = cond_dir / c / f"{u.utt_id}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(make_wav(0.2 + 0.01 * i + (0.05 if c == "C4" else 0)))  # distinct audio
    return utts, cond_dir


class FakePrisma:
    """Returns a transcript per (file, format); counts calls."""

    def __init__(self, fail_on: str | None = None, auth_fail: bool = False) -> None:
        self.calls: list[tuple[str, PrismaSettings]] = []
        self.fail_on = fail_on
        self.auth_fail = auth_fail

    def is_cached(self, audio: bytes, settings: PrismaSettings) -> bool:
        return False

    def transcribe(self, audio: bytes, filename: str, settings: PrismaSettings) -> TranscriptResult:
        self.calls.append((filename, settings))
        if self.auth_fail:
            raise ApiAuthError("403", 403)
        if self.fail_on and self.fail_on in filename:
            raise RuntimeError("boom")
        if filename.startswith("num01"):
            text = "25 ரூபாய்" if settings.format == "transcribe" else "இருபத்தி அஞ்சு ரூபாய்"
        else:
            text = "அவங்க நாளைக்கு வருவாங்கோ"
        return TranscriptResult(text, latency_ms=100.0 + len(self.calls), cached=False)


def test_plan_counts_and_shared_calls(setup) -> None:
    utts, cond_dir = setup
    jobs, missing = runner.plan_jobs(utts, ["C1", "C4", "C2"], runner.SETTINGS, ("அவங்க",), cond_dir)
    assert len(jobs) == 3 * 2 * 4  # 3 utterances x 2 conditions with audio x 4 settings
    assert len(missing) == 3  # C2 has no audio
    # F3 shares F2's call: 3 Prisma calls per (utt, condition)
    assert len(runner.unique_calls(jobs)) == 3 * 2 * 3


def test_without_bias_words_f2_shares_f1_call(setup) -> None:
    utts, cond_dir = setup
    jobs, _ = runner.plan_jobs(utts, ["C1"], runner.SETTINGS, (), cond_dir)
    assert len(runner.unique_calls(jobs)) == 3 * 2  # F0 and F1 only


def test_records_scores_and_lexicon_only_in_f3(setup) -> None:
    utts, cond_dir = setup
    jobs, _ = runner.plan_jobs(utts, ["C1"], runner.SETTINGS, (), cond_dir)
    fake = FakePrisma()
    results = runner.run_calls(jobs, fake, workers=2)
    lex = Lexicon([Rule("வருவாங்கோ", "வருவாங்க", "dialect")])
    records = runner.build_records(jobs, results, lex)
    by = {(r["utt_id"], r["setting"]): r for r in records}
    assert by[("real01", "F2")]["hypothesis"] == "அவங்க நாளைக்கு வருவாங்கோ"
    assert by[("real01", "F3")]["hypothesis"] == "அவங்க நாளைக்கு வருவாங்க"
    assert by[("real01", "F3")]["char_edits"] == 0 and by[("real01", "F3")]["lexicon_hits"] == ["வருவாங்கோ"]
    # ITN output "25" matches the digit variant and the number
    f1 = by[("num01__Trisha", "F1")]
    assert f1["char_edits"] == 0 and f1["num_matched"] == 1
    f0 = by[("num01__Trisha", "F0")]
    assert f0["num_matched"] == 1  # "இருபத்தி அஞ்சு" is still 25
    assert f0["char_edits"] > 0


def test_summary_structure_and_latency_once_per_call(setup) -> None:
    utts, cond_dir = setup
    jobs, _ = runner.plan_jobs(utts, ["C1", "C4"], runner.SETTINGS, ("அவங்க",), cond_dir)
    fake = FakePrisma()
    records = runner.build_records(jobs, runner.run_calls(jobs, fake), Lexicon([]))
    summary = runner.summarize_run(records, {"split": "dev", "settings": list(runner.SETTINGS)})
    run = summary["run"]
    assert run["prisma_calls"]["unique"] == len(fake.calls) == 18
    assert run["latency_ms"]["n"] == 18 and run["n_failures"] == 0
    row = next(r for r in summary["overall"] if r["source"] == "timbre" and r["condition"] == "C1" and r["setting"] == "F0")
    assert row["n"] == 2 and set(row["cer"]) == {"value", "low", "high", "n"}
    assert {r["category"] for r in summary["by_category"]} == {"numbers", "colloquial"}
    assert {r["dialect"] for r in summary["by_dialect"]} == {"madurai"}
    json.dumps(summary)  # serialisable
    md = summary_markdown(summary)
    assert "C1 Clean 16 kHz" in md and "n |" in md and "%" in md


def test_failures_are_recorded_and_excluded(setup) -> None:
    utts, cond_dir = setup
    jobs, _ = runner.plan_jobs(utts, ["C1"], ["F0"], (), cond_dir)
    records = runner.build_records(jobs, runner.run_calls(jobs, FakePrisma(fail_on="real01")), Lexicon([]))
    summary = runner.summarize_run(records, {"split": "dev"})
    assert summary["run"]["n_failures"] == 1
    real = next(r for r in summary["overall"] if r["source"] == "real")
    assert real["failures"] == 1 and real["n"] == 0


def test_auth_error_stops_run(setup) -> None:
    utts, cond_dir = setup
    jobs, _ = runner.plan_jobs(utts, ["C1"], ["F0"], (), cond_dir)
    with pytest.raises(ApiAuthError):
        runner.run_calls(jobs, FakePrisma(auth_fail=True), workers=1)


def test_rerun_makes_zero_new_calls_with_real_client(setup, mock_api, cache, no_sleep) -> None:
    utts, cond_dir = setup
    route = mock_api.post(STT).respond(200, json={"success": True, "transcript": "சரி"})
    client = PrismaClient(api_key="k", cache=cache, sleep=no_sleep.append)
    jobs, _ = runner.plan_jobs(utts, ["C1"], runner.SETTINGS, ("அவங்க",), cond_dir)
    assert runner.count_new_calls(jobs, client) == (9, 9)
    runner.run_calls(jobs, client)
    assert route.call_count == 9
    assert runner.count_new_calls(jobs, client) == (0, 9)
    results = runner.run_calls(jobs, client)
    assert route.call_count == 9
    records = runner.build_records(jobs, results, Lexicon([]))
    assert runner.summarize_run(records, {})["run"]["prisma_calls"]["new"] == 0


def test_word_substitutions_and_error_list() -> None:
    assert word_substitutions("அவர்கள் நாளை வருவார்கள்", "அவங்க நாளை வருவாங்க") == [
        ("அவர்கள்", "அவங்க"),
        ("வருவார்கள்", "வருவாங்க"),
    ]
    rec = {"error": None, "utt_id": "x", "condition": "C1", "setting": "F0", "char_edits": 3,
           "char_ref": 10, "ref_used": "அவர்கள் வந்தாங்க", "hyp_norm": "அவங்க வந்தாங்க"}  # fmt: skip
    md = errors_markdown([rec])
    assert "| அவர்கள் | அவங்க | 1 |" in md
