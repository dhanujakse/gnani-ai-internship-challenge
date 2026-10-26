from pathlib import Path

import soundfile as sf

from kuralcheck import synth
from kuralcheck.budget import confirm_calls
from kuralcheck.clients.timbre import TimbreClient
from kuralcheck.data import Sentence, utterances
from tests.conftest import make_wav

TTS = "/api/v1/tts/inference"


def sentences() -> list[Sentence]:
    return [
        Sentence("num01", "இருபத்தைந்து ரூபாய்", (), "numbers", "standard", "timbre", ("Trisha", "Asmita"), "dev"),
        Sentence("real01", "அவங்க வந்தாங்க", (), "colloquial", "madurai", "real", ("S01",), "test"),
    ]


def test_plan_skips_real_and_existing(tmp_path: Path) -> None:
    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    (tmp_path / "num01__Asmita.wav").write_bytes(make_wav(0.1))
    jobs = synth.plan(utts, "timbre-v2.5")
    assert [j.utt.utt_id for j in jobs] == ["num01__Trisha"]


def test_run_writes_16k_wavs_and_counts_calls(tmp_path, mock_api, cache, no_sleep) -> None:
    route = mock_api.post(TTS).respond(200, content=make_wav(0.5, sr=22050))  # converted to 16 kHz
    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    jobs = synth.plan(utts, "timbre-v2.5")
    client = TimbreClient(api_key="k", cache=cache, sleep=no_sleep.append)
    made, errors = synth.run(jobs, client, workers=2)
    assert errors == [] and made == 2 and route.call_count == 2
    for j in jobs:
        info = sf.info(j.utt.source_audio)
        assert info.samplerate == 16000 and info.channels == 1

    # files deleted but cache kept: regenerating costs nothing
    for j in jobs:
        j.utt.source_audio.unlink()
    made_again, _ = synth.run(synth.plan(utts, "timbre-v2.5"), client, workers=2)
    assert made_again == 0 and route.call_count == 2


def test_run_reports_failures_and_continues(tmp_path, mock_api, cache, no_sleep) -> None:
    mock_api.post(TTS).respond(400)
    utts = utterances(sentences(), timbre_dir=tmp_path, real_dir=tmp_path)
    client = TimbreClient(api_key="k", cache=cache, sleep=no_sleep.append)
    made, errors = synth.run(synth.plan(utts, "timbre-v2.5"), client)
    assert made == 0 and len(errors) == 2


def test_confirm_calls_rules() -> None:
    assert confirm_calls(100, "Prisma", interactive=False)  # at the limit: no prompt
    assert not confirm_calls(101, "Prisma", interactive=False)  # needs --yes
    assert confirm_calls(101, "Prisma", yes=True, interactive=False)
    assert confirm_calls(500, "Prisma", ask=lambda _: "y", interactive=True)
    assert not confirm_calls(500, "Prisma", ask=lambda _: "", interactive=True)
