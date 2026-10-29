import asyncio
import json
import time

import httpx
import pytest

from sarvagyan_server.languages import clamp_speed, get_language, voice_for
from sarvagyan_server.providers.base import ProviderError
from sarvagyan_server.providers.gnani_stt import _status_error
from sarvagyan_server.providers.mymemory import MyMemoryTranslator, split_for_limit
from sarvagyan_server.realtime import EchoGuard, Participant, PlaybackDispatcher, Utterance
from tests.fakes import FakeSynth


def test_echo_guard_matches_translated_speech_only_recently() -> None:
    g = EchoGuard(window_s=10)
    g.register("I will call you back in five minutes.", now=100)
    assert g.is_echo("i will call you back in five minutes", now=105)
    assert g.is_echo("I'll call you back in five minutes", now=105)  # close paraphrase of the same audio
    assert not g.is_echo("Where are you right now?", now=105)
    assert not g.is_echo("I will call you back in five minutes", now=200)  # outside the window
    assert g.blocked == 2


def test_languages_and_voices() -> None:
    assert get_language("ta-IN").native == "தமிழ்"
    assert voice_for("en-IN", "Trisha") == "Kaveri"  # a Tamil voice cannot speak the English slot
    assert voice_for("ta-IN", "Asmita") == "Asmita"
    assert clamp_speed(2.0) == 1.15 and clamp_speed(0.1) == 0.85 and clamp_speed(None) == 1.0
    with pytest.raises(ValueError):
        get_language("fr-FR")


def test_split_respects_500_byte_limit() -> None:
    long = "நான் நாளைக்கு கடைக்கு வருவேன். " * 30
    parts = split_for_limit(long)
    assert len(parts) > 1 and all(len(p.encode()) <= 480 for p in parts)
    assert " ".join(parts).split() == long.split()
    assert split_for_limit("short") == ["short"]


def _mm(handler) -> MyMemoryTranslator:
    return MyMemoryTranslator(email="dev@example.com", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_mymemory_parses_and_caches() -> None:
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(dict(req.url.params))
        return httpx.Response(200, json={"responseData": {"translatedText": "My phone isn&#39;t charging"},
                                         "responseStatus": 200, "quotaFinished": False})  # fmt: skip

    tr = _mm(handler)
    assert await tr.translate("என் போன் சார்ஜ் ஆகவில்லை", "ta-IN", "en-IN") == "My phone isn't charging"
    assert await tr.translate("என் போன் சார்ஜ் ஆகவில்லை", "ta-IN", "en-IN") == "My phone isn't charging"
    assert len(seen) == 1 and seen[0]["langpair"] == "ta|en" and seen[0]["de"] == "dev@example.com"
    assert await tr.translate("same", "en-IN", "en-IN") == "same" and len(seen) == 1


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(200, json={"responseData": {"translatedText": "x"}, "responseStatus": 200, "quotaFinished": True}), "quota"),
        (httpx.Response(200, json={"responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"},
                                   "responseStatus": 429}), "quota"),
        (httpx.Response(429, text="slow down"), "rate_limited"),
        (httpx.Response(503, text="down"), "server"),
        (httpx.Response(200, text="<html>"), "server"),
    ],
)
async def test_mymemory_error_mapping(response, code) -> None:
    tr = _mm(lambda req: response)
    with pytest.raises(ProviderError) as e:
        await tr.translate("வணக்கம்", "ta-IN", "en-IN")
    assert e.value.code == code


async def test_mymemory_timeout() -> None:
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(ProviderError) as e:
        await _mm(handler).translate("வணக்கம்", "ta-IN", "en-IN")
    assert e.value.code == "timeout" and e.value.retryable


def test_gnani_status_mapping() -> None:
    assert _status_error(401).code == "auth" and "GNANI_API_KEY" in _status_error(401).message
    assert _status_error(403).code == "auth"
    assert _status_error(429).code == "rate_limited" and _status_error(429).retryable
    assert _status_error(503).code == "server"


class _Room:
    def __init__(self) -> None:
        self.synthesizer = FakeSynth()
        self.events: list = []

    async def update(self, utt, stage):
        utt.stage = stage
        self.events.append(("stage", utt.id, stage))

    async def send(self, part, item):
        self.events.append(("send", item if isinstance(item, dict) else len(item)))

    async def error(self, *a, **k):
        self.events.append(("error",))


async def test_late_translations_are_subtitled_not_spoken() -> None:
    room = _Room()
    lis = Participant("u2", "B", language="en-IN", connected=True)
    disp = PlaybackDispatcher(room, lis)  # type: ignore[arg-type]
    old = Utterance("x-a1", "u1", 1, "பழையது", "ta-IN", t_final=time.monotonic() - 60, translation="old", target_lang="en-IN")
    new = Utterance("x-a2", "u1", 2, "புதியது", "ta-IN", t_final=time.monotonic(), translation="new", target_lang="en-IN")
    disp.submit(old)
    disp.submit(new)
    for _ in range(50):
        await asyncio.sleep(0.01)
        if ("stage", "x-a2", "done") in room.events:
            break
    await disp.stop()
    assert ("stage", "x-a1", "skipped") in room.events and old.error
    assert [c[0] for c in room.synthesizer.calls] == ["new"]
    assert lis.echo.is_echo("new")  # what B heard is remembered for echo rejection


def test_event_has_no_audio_or_secrets() -> None:
    u = Utterance("i", "s", 1, "வணக்கம்", "ta-IN", 0.0, translation="Hello")
    assert set(json.loads(json.dumps(u.event()))) >= {"id", "stage", "original", "translation", "metrics", "rev"}


class _FakeTtsWs:
    """Replays Gnani's observed message order, including the stray extra `complete`."""

    def __init__(self) -> None:
        import base64 as b64

        audio = json.dumps({"type": "audio", "data": {"audio": b64.b64encode(b"\x01\x00" * 8).decode(), "is_final": False}})
        self._script = [
            json.dumps({"type": "start"}), audio, json.dumps({"type": "complete", "data": {"is_final": True}}),
            json.dumps({"type": "complete"}),  # stray message that used to end the NEXT request instantly
            json.dumps({"type": "start"}), audio, audio, json.dumps({"type": "complete", "data": {"is_final": True}}),
        ]  # fmt: skip
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        return self._script.pop(0)

    async def close(self) -> None:
        pass


async def test_tts_ignores_stray_complete_between_requests() -> None:
    from sarvagyan_server.providers.gnani_tts import GnaniSynthesizer

    synth = GnaniSynthesizer("k", "wss://example")
    ws = _FakeTtsWs()

    async def conn():
        return ws

    synth._connection = conn  # type: ignore[method-assign]
    first = [c async for c in synth.synthesize("Hello", "en-IN", "Kaveri", 1.0)]
    second = [c async for c in synth.synthesize("சரி", "ta-IN", "Trisha", 1.0)]
    assert len(first) == 1 and len(second) == 2
    assert json.loads(ws.sent[1])["language"] == "ta-IN"
