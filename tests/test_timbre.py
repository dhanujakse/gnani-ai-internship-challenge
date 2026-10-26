import json

import httpx
import pytest
import respx

from kuralcheck.clients.errors import ApiAuthError, ApiError
from kuralcheck.clients.timbre import TimbreClient, TimbreSettings
from tests.conftest import make_wav

TTS = "/api/v1/tts/inference"


def client(cache, sleeps: list[float]) -> TimbreClient:
    return TimbreClient(api_key="test-key", cache=cache, sleep=sleeps.append)


def test_sends_expected_json_and_returns_wav(mock_api: respx.MockRouter, cache, no_sleep) -> None:
    audio = make_wav(0.5)
    route = mock_api.post(TTS).respond(200, content=audio, headers={"content-type": "audio/wav"})
    res = client(cache, no_sleep).synthesize(
        "வணக்கம்", TimbreSettings(voice="Trisha", model="timbre-v2.5")
    )
    assert res.audio == audio and res.cached is False
    req = route.calls.last.request
    assert req.headers["X-API-Key-ID"] == "test-key"
    assert json.loads(req.content) == {
        "text": "வணக்கம்",
        "model": "timbre-v2.5",
        "voice": "Trisha",
        "language": "ta-IN",
        "audio_config": {"sample_rate": 16000, "container": "wav"},
    }


def test_cache_hit_on_second_call(mock_api, cache, no_sleep) -> None:
    route = mock_api.post(TTS).respond(200, content=make_wav(0.2))
    c = client(cache, no_sleep)
    s = TimbreSettings(voice="Brinda")
    c.synthesize("சரி", s)
    second = c.synthesize("சரி", s)
    assert route.call_count == 1 and second.cached is True


def test_other_voice_is_a_new_call(mock_api, cache, no_sleep) -> None:
    route = mock_api.post(TTS).respond(200, content=make_wav(0.2))
    c = client(cache, no_sleep)
    c.synthesize("சரி", TimbreSettings(voice="Brinda"))
    c.synthesize("சரி", TimbreSettings(voice="Trisha"))
    assert route.call_count == 2


def test_digits_rejected_numbers_must_be_words(mock_api, cache, no_sleep) -> None:
    route = mock_api.post(TTS).respond(200, content=make_wav(0.2))
    with pytest.raises(ValueError, match="words"):
        client(cache, no_sleep).synthesize("10 ரூபாய்", TimbreSettings(voice="Trisha"))
    assert route.call_count == 0


def test_non_audio_200_is_an_error(mock_api, cache, no_sleep) -> None:
    mock_api.post(TTS).respond(200, json={"error": "voice not found"})
    with pytest.raises(ApiError):
        client(cache, no_sleep).synthesize("சரி", TimbreSettings(voice="Trisha"))
    assert cache.count("timbre") == 0


def test_retry_then_auth_error_not_retried(mock_api, cache, no_sleep) -> None:
    route = mock_api.post(TTS).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, content=make_wav(0.2))]
    )
    assert client(cache, no_sleep).synthesize("சரி", TimbreSettings(voice="Trisha")).audio
    assert route.call_count == 2

    mock_api.post(TTS).respond(403)
    with pytest.raises(ApiAuthError):
        client(cache, no_sleep).synthesize("வாங்க", TimbreSettings(voice="Trisha"))


def test_v25_voice_must_be_tamil() -> None:
    with pytest.raises(ValueError):
        TimbreSettings(voice="Nalini", model="timbre-v2.5")
    TimbreSettings(voice="Shivani", model="timbre-v3.0")  # v3.0 voices speak all languages
