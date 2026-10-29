"""Fake providers for offline tests. A client "speaks" by sending a binary frame b"SAY:<lang>:<text>"."""

import asyncio
from collections.abc import AsyncIterator

from sarvagyan_server.providers.base import ProviderError, SttEvent

_END = object()


class FakeSttSession:
    def __init__(self, language: str | None, log: list) -> None:
        self.language = language
        self.frames = 0
        self._q: asyncio.Queue = asyncio.Queue()
        self._log = log
        self.closed = False

    async def send_audio(self, frame: bytes) -> None:
        self.frames += 1
        if frame.startswith(b"SAY:"):
            _, lang, text = frame.decode().split(":", 2)
            await self._q.put(SttEvent("speech_start"))
            await self._q.put(SttEvent("transcript", text=text, language=lang or None, latency_ms=111, audio_ms=900))
        elif frame.startswith(b"ERR:"):
            await self._q.put(SttEvent("error", message="engine hiccup"))

    async def update_language(self, language: str | None) -> None:
        self.language = language
        self._log.append(("update_language", language))

    async def commit(self) -> None:
        pass

    async def events(self) -> AsyncIterator[SttEvent]:
        while True:
            ev = await self._q.get()
            if ev is _END:
                return
            yield ev

    async def close(self) -> None:
        self.closed = True
        await self._q.put(_END)


class FakeRecognizer:
    def __init__(self) -> None:
        self.sessions: list[FakeSttSession] = []
        self.log: list = []
        self.fail_with: ProviderError | None = None

    async def open(self, language: str | None, sample_rate: int = 16000) -> FakeSttSession:
        if self.fail_with:
            raise self.fail_with
        s = FakeSttSession(language, self.log)
        self.sessions.append(s)
        return s


class FakeTranslator:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail = False
        self.delay = 0.0

    async def translate(self, text: str, source: str, target: str) -> str:
        self.calls.append((text, source, target))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ProviderError("fake", "timeout", "Translation timed out.")
        return f"[{target}] {text}"


class FakeSynth:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, float]] = []
        self.fail = False

    async def synthesize(self, text: str, language: str, voice: str, speed: float, sample_rate: int = 16000):
        self.calls.append((text, language, voice, speed))
        if self.fail:
            raise ProviderError("fake-tts", "server", "voice engine down")
        yield b"\x01\x00" * 160
        await asyncio.sleep(0)
        yield b"\x02\x00" * 160
