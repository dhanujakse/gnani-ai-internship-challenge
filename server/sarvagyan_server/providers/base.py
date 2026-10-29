"""Provider interfaces. Each AI service sits behind a small protocol so it can be swapped
(e.g. another STT, a paid translator, or a speech-to-speech model) without touching the pipeline."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

ErrorCode = Literal[
    "auth", "rate_limited", "quota", "unsupported_language", "timeout", "network", "bad_request", "server", "closed"
]
RETRYABLE: set[str] = {"rate_limited", "timeout", "network", "server", "closed"}


class ProviderError(Exception):
    """A provider failure with a user-safe message (never contains keys or conversation content)."""

    def __init__(self, provider: str, code: ErrorCode, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.code: ErrorCode = code
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE


@dataclass(frozen=True)
class SttEvent:
    kind: Literal["ready", "speech_start", "processing", "transcript", "error"]
    text: str = ""
    language: str | None = None  # detected language (Prisma v3.0), else None
    latency_ms: int | None = None
    segment_index: int | None = None
    audio_ms: int | None = None
    message: str = ""


class SttSession(Protocol):
    async def send_audio(self, frame: bytes) -> None: ...
    async def update_language(self, language: str | None) -> None: ...
    async def commit(self) -> None: ...
    def events(self) -> AsyncIterator[SttEvent]: ...
    async def close(self) -> None: ...


class SpeechRecognizer(Protocol):
    """Streaming speech-to-text. language=None means automatic language detection."""

    async def open(self, language: str | None, sample_rate: int = 16000) -> SttSession: ...


class Translator(Protocol):
    name: str

    async def translate(self, text: str, source: str, target: str) -> str: ...


class SpeechSynthesizer(Protocol):
    """Streaming text-to-speech: yields raw 16-bit mono PCM chunks at `sample_rate`."""

    def synthesize(
        self, text: str, language: str, voice: str, speed: float, sample_rate: int
    ) -> AsyncIterator[bytes]: ...
