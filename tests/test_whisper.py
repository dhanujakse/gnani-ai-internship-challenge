from dataclasses import dataclass

from kuralcheck import runner
from kuralcheck.clients.whisper_local import WhisperLocal
from kuralcheck.data import utterances
from kuralcheck.fixlayer.lexicon import Lexicon
from tests.conftest import make_wav
from tests.test_runner import sentences


@dataclass
class Seg:
    text: str


class FakeModel:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, path: str, **kwargs):
        self.calls += 1
        assert kwargs["language"] == "ta"
        return iter([Seg(" அவங்க நாளைக்கு "), Seg("வருவாங்க ")]), None


def test_transcribe_joins_segments_and_caches(cache, wav) -> None:
    model = FakeModel()
    w = WhisperLocal(cache, model=model)
    first = w.transcribe(wav, "a.wav")
    assert first.transcript == "அவங்க நாளைக்கு வருவாங்க" and not first.cached
    assert w.is_cached(wav)
    second = w.transcribe(wav, "a.wav")
    assert second.cached and model.calls == 1
    assert w.name == "whisper-small"


def test_runs_through_the_same_runner(tmp_path, cache) -> None:
    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    for i, u in enumerate(utts):
        p = tmp_path / "cond" / "C1" / f"{u.utt_id}.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(make_wav(0.2 + 0.01 * i))
    jobs, _ = runner.plan_jobs(utts, ["C1"], ["F0"], (), tmp_path / "cond")
    w = WhisperLocal(cache, model=FakeModel())
    records = runner.build_records(jobs, runner.run_calls(jobs, w), Lexicon([]), model=w.name)
    summary = runner.summarize_run(records, {"split": "test"})
    assert {r["model"] for r in summary["overall"]} == {"whisper-small"}
    real = next(r for r in summary["overall"] if r["source"] == "real")
    assert real["cer"]["value"] == 0.0
