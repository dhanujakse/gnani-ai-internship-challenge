import json
from pathlib import Path

import pytest
from PIL import Image

from kuralcheck import runner
from kuralcheck.data import Sentence, utterances
from kuralcheck.fixlayer.lexicon import Lexicon
from kuralcheck.report.runs import latest, list_runs
from kuralcheck.report.scorecard import make_scorecard, scorecard_data
from kuralcheck.report.tables import (
    comparison_markdown,
    readme_results_block,
    replace_readme_block,
    summary_markdown,
)
from tests.test_runner import FakePrisma, sentences


@pytest.fixture
def summary(tmp_path: Path) -> dict:
    cond_dir = tmp_path / "conditions"
    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    from tests.conftest import make_wav

    for i, u in enumerate(utts):
        for c in ("C1", "C2", "C3", "C4"):
            p = cond_dir / c / f"{u.utt_id}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(make_wav(0.2 + 0.01 * i + 0.003 * int(c[1])))
    jobs, _ = runner.plan_jobs(utts, ["C1", "C2", "C3", "C4"], runner.SETTINGS, ("அவங்க",), cond_dir)
    records = runner.build_records(jobs, runner.run_calls(jobs, FakePrisma()), Lexicon([]))
    return runner.summarize_run(records, {"split": "test", "settings": list(runner.SETTINGS),
                                          "models": {"stt_version": "Prisma v2.5", "tts": "timbre-v2.5"}})  # fmt: skip


def whisper_from(summary: dict) -> dict:
    w = json.loads(json.dumps(summary))
    w["overall"] = [dict(r, model="whisper-small", setting="W0") for r in w["overall"] if r["setting"] == "F0"]
    return w


def test_scorecard_numbers_match_summary(summary) -> None:
    data = scorecard_data(summary)
    assert data["headline_source"] == "real"
    for entry in data["cer_by_condition"]:
        row = next(r for r in summary["overall"]
                   if r["source"] == "real" and r["condition"] == entry["condition"] and r["setting"] == "F0")  # fmt: skip
        assert entry["baseline"] == row["cer"]
    assert data["latency_ms"] == summary["run"]["latency_ms"]
    assert data["n_by_source"] == {"real": 1, "timbre": 2}


def test_scorecard_png_is_1200_square(summary, tmp_path) -> None:
    (tmp_path / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    data = make_scorecard(tmp_path / "summary.json")
    with Image.open(tmp_path / "scorecard.png") as img:
        assert img.size == (1200, 1200)
    assert json.loads((tmp_path / "scorecard.json").read_text(encoding="utf-8")) == json.loads(json.dumps(data))


def test_scorecard_with_whisper(summary, tmp_path) -> None:
    (tmp_path / "s.json").write_text(json.dumps(summary), encoding="utf-8")
    (tmp_path / "w.json").write_text(json.dumps(whisper_from(summary)), encoding="utf-8")
    data = make_scorecard(tmp_path / "s.json", tmp_path, tmp_path / "w.json")
    assert data["whisper_model"] == "whisper-small"
    assert all("whisper" in e for e in data["cer_by_condition"])


def test_tables_show_n_and_ci(summary) -> None:
    md = summary_markdown(summary)
    assert "## Real recordings" in md and "## Synthetic" in md
    assert "Number accuracy" in md and "by category" in md and "by dialect" in md
    row = next(line for line in md.splitlines() if line.startswith("| C1 Clean 16 kHz | 1 |"))
    assert "(" in row and "–" in row


def test_comparison_table(summary) -> None:
    md = comparison_markdown(summary, whisper_from(summary), "timbre")
    assert "whisper-small" in md and md.count("\n| C") == 4


def test_readme_block_replace(summary) -> None:
    readme = "# X\n\n<!-- results:start -->\nold\n<!-- results:end -->\n\nmore\n"
    block = readme_results_block("2026-10-31_test", summary, whisper_from(summary))
    new = replace_readme_block(readme, block)
    assert "old" not in new and "results/2026-10-31_test/scorecard.png" in new and new.endswith("more\n")
    with pytest.raises(ValueError):
        replace_readme_block("no markers", block)


def test_runs_discovery(summary, tmp_path) -> None:
    for name, s in (("2026-10-30_test", summary), ("2026-10-31_test", summary),
                    ("2026-10-31_test_whisper", whisper_from(summary))):  # fmt: skip
        (tmp_path / name).mkdir()
        (tmp_path / name / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    assert len(list_runs(tmp_path)) == 3
    assert latest("test", results_dir=tmp_path).name == "2026-10-31_test"
    assert latest("test", whisper=True, results_dir=tmp_path).name == "2026-10-31_test_whisper"
    assert latest("dev", results_dir=tmp_path) is None
