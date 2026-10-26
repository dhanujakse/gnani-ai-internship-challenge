import json

import httpx
import pytest
import respx

from kuralcheck.cache import Cache
from kuralcheck.clients.errors import (
    ApiAuthError,
    ApiBadRequest,
    ApiError,
    ApiRateLimited,
    ApiServerError,
)
from kuralcheck.clients.prisma import (
    PrismaClient,
    PrismaSettings,
    validate_bias_list,
)
from tests.conftest import make_wav

STT = "/stt/v3"
OK = {"success": True, "request_id": "r1", "timestamp": "t", "transcript": "வணக்கம் எப்படி இருக்கீங்க"}


def client(cache: Cache | None, sleeps: list[float]) -> PrismaClient:
    return PrismaClient(api_key="test-key", cache=cache, sleep=sleeps.append)


def test_success_sends_expected_request(mock_api: respx.MockRouter, cache, wav, no_sleep) -> None:
    route = mock_api.post(STT).respond(200, json=OK)
    res = client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings(format="transcribe"))
    assert res.transcript == OK["transcript"]
    assert res.cached is False and res.latency_ms >= 0
    req = route.calls.last.request
    assert req.headers["X-API-Key-ID"] == "test-key"
    body = req.content
    assert b'name="audio_file"' in body and b'name="language_code"' in body and b"ta-IN" in body
    assert b'name="format"' in body and b"transcribe" in body
    assert b'name="bias_list"' not in body  # nothing to boost


def test_bias_list_sent_as_json(mock_api, cache, wav, no_sleep) -> None:
    route = mock_api.post(STT).respond(200, json=OK)
    s = PrismaSettings(format="transcribe", bias_list=("அவங்க", "வாங்க"), bias_score=1.0)
    client(cache, no_sleep).transcribe(wav, "a.wav", s)
    body = route.calls.last.request.content
    assert json.dumps(["அவங்க", "வாங்க"], ensure_ascii=False).encode() in body
    assert b'name="bias_score"' in body


def test_second_call_hits_cache(mock_api, cache, wav, no_sleep) -> None:
    route = mock_api.post(STT).respond(200, json=OK)
    c = client(cache, no_sleep)
    first = c.transcribe(wav, "a.wav", PrismaSettings())
    second = c.transcribe(wav, "a.wav", PrismaSettings())
    assert route.call_count == 1
    assert second.cached is True and second.transcript == first.transcript
    assert second.latency_ms == first.latency_ms  # original latency is kept


def test_different_settings_are_not_shared_in_cache(mock_api, cache, wav, no_sleep) -> None:
    route = mock_api.post(STT).respond(200, json=OK)
    c = client(cache, no_sleep)
    c.transcribe(wav, "a.wav", PrismaSettings(format="verbatim"))
    c.transcribe(wav, "a.wav", PrismaSettings(format="transcribe"))
    assert route.call_count == 2


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retries_once_then_succeeds(mock_api, cache, wav, no_sleep, status) -> None:
    route = mock_api.post(STT).mock(
        side_effect=[httpx.Response(status), httpx.Response(200, json=OK)]
    )
    res = client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings())
    assert res.transcript == OK["transcript"]
    assert route.call_count == 2
    assert len(no_sleep) == 1 and 0 < no_sleep[0] <= 3


@pytest.mark.parametrize(
    ("status", "exc"), [(429, ApiRateLimited), (500, ApiServerError), (503, ApiServerError)]
)
def test_gives_up_after_one_retry(mock_api, cache, wav, no_sleep, status, exc) -> None:
    route = mock_api.post(STT).respond(status)
    with pytest.raises(exc):
        client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings())
    assert route.call_count == 2


@pytest.mark.parametrize(("status", "exc"), [(400, ApiBadRequest), (403, ApiAuthError)])
def test_never_retries_400_403(mock_api, cache, wav, no_sleep, status, exc) -> None:
    route = mock_api.post(STT).respond(status, json={"detail": "nope"})
    with pytest.raises(exc):
        client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings())
    assert route.call_count == 1 and no_sleep == []


def test_timeout_retried_once(mock_api, cache, wav, no_sleep) -> None:
    route = mock_api.post(STT).mock(
        side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, json=OK)]
    )
    assert client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings()).transcript
    assert route.call_count == 2


def test_success_false_is_an_error(mock_api, cache, wav, no_sleep) -> None:
    mock_api.post(STT).respond(200, json={"success": False, "transcript": ""})
    with pytest.raises(ApiError):
        client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings())


def test_failures_are_not_cached(mock_api, cache, wav, no_sleep) -> None:
    mock_api.post(STT).respond(400)
    with pytest.raises(ApiBadRequest):
        client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings())
    assert cache.count("prisma") == 0


def test_rejects_audio_over_60_seconds(mock_api, cache, no_sleep) -> None:
    route = mock_api.post(STT).respond(200, json=OK)
    with pytest.raises(ValueError, match="60"):
        client(cache, no_sleep).transcribe(make_wav(61), "long.wav", PrismaSettings())
    assert route.call_count == 0


def test_error_message_never_contains_key(mock_api, cache, wav, no_sleep) -> None:
    mock_api.post(STT).respond(403, text="bad key test-key")
    with pytest.raises(ApiAuthError) as e:
        client(cache, no_sleep).transcribe(wav, "a.wav", PrismaSettings())
    assert "test-key" not in str(e.value)


def test_missing_key_fails_fast(cache) -> None:
    with pytest.raises(ValueError, match="GNANI_API_KEY"):
        PrismaClient(api_key="", cache=cache)


# --- bias_list validation (Prisma silently ignores invalid lists, so we must check locally)


def test_valid_bias_list_tamil_and_english() -> None:
    assert validate_bias_list(["அவங்க", "கொடுங்க", "UPI"]) == ["அவங்க", "கொடுங்க", "UPI"]


@pytest.mark.parametrize(
    "bad",
    [
        ["இரண்டு வார்த்தை"],  # two words
        ["abc123"],  # digit
        ["சரி!"],  # punctuation
        [""],  # empty
        ["அ"] * 101,  # too many
    ],
)
def test_invalid_bias_list_raises(bad: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_bias_list(bad)


def test_invalid_bias_list_raises_before_any_call(mock_api, cache, wav, no_sleep) -> None:
    route = mock_api.post(STT).respond(200, json=OK)
    with pytest.raises(ValueError):
        client(cache, no_sleep).transcribe(
            wav, "a.wav", PrismaSettings(bias_list=("two words",), bias_score=1.0)
        )
    assert route.call_count == 0


def test_invalid_bias_score_raises() -> None:
    with pytest.raises(ValueError):
        PrismaSettings(bias_list=("அவங்க",), bias_score=0.7)
