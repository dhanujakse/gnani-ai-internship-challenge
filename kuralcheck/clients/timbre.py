"""Gnani Timbre text-to-speech (REST, POST /api/v1/tts/inference) -> 16 kHz WAV, cached."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from kuralcheck.cache import Cache, make_key
from kuralcheck.clients._http import post_with_retry
from kuralcheck.clients.errors import ApiError
from kuralcheck.config import Settings, get_settings
from kuralcheck.throttle import Throttle, shared_throttle

ENDPOINT = "/api/v1/tts/inference"
TIMEOUT_S = 20.0
TAMIL_VOICES_V25 = ("Asmita", "Trisha", "Brinda", "Vedika", "Noopur")
DEFAULT_VOICES = ("Trisha", "Asmita", "Brinda")  # the 3 voices used for the test set
_DIGITS = re.compile(r"\d")


@dataclass(frozen=True)
class TimbreSettings:
    voice: str
    model: Literal["timbre-v2.5", "timbre-v3.0"] = "timbre-v2.5"
    language: str = "ta-IN"
    sample_rate: int = 16000
    container: Literal["wav", "mp3", "ogg"] = "wav"

    def __post_init__(self) -> None:
        if self.model == "timbre-v2.5" and self.voice not in TAMIL_VOICES_V25:
            raise ValueError(f"{self.voice} is not a timbre-v2.5 Tamil voice; use one of {TAMIL_VOICES_V25}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint": ENDPOINT,
            "model": self.model,
            "voice": self.voice,
            "language": self.language,
            "sample_rate": self.sample_rate,
            "container": self.container,
        }


@dataclass(frozen=True)
class SynthesisResult:
    audio: bytes
    latency_ms: float
    cached: bool


def _looks_like_audio(data: bytes, container: str) -> bool:
    if container == "wav":
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if container == "ogg":
        return data[:4] == b"OggS"
    return len(data) > 0 and not data.lstrip()[:1] in (b"{", b"[", b"<")


class TimbreClient:
    def __init__(
        self,
        api_key: str,
        cache: Cache | None,
        base_url: str = "https://api.vachana.ai",
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        throttle: Throttle | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GNANI_API_KEY is not set (add it to .env or Streamlit secrets)")
        self._key = api_key
        self._cache = cache
        self._url = base_url.rstrip("/") + ENDPOINT
        self._http = http or httpx.Client(timeout=TIMEOUT_S)
        self._sleep = sleep
        self._throttle = throttle

    @classmethod
    def from_settings(cls, settings: Settings | None = None, cache: Cache | None = None) -> "TimbreClient":
        s = settings or get_settings()
        return cls(s.gnani_api_key.get_secret_value(), cache or Cache(s.cache_path), s.gnani_base_url,
                   throttle=shared_throttle(s.gnani_calls_per_second, s.gnani_max_calls_per_second))

    def cache_key(self, text: str, settings: TimbreSettings) -> str:
        return make_key("timbre", text.encode("utf-8"), settings.as_dict())

    def is_cached(self, text: str, settings: TimbreSettings) -> bool:
        return self._cache is not None and self._cache.has(self.cache_key(text, settings))

    def synthesize(self, text: str, settings: TimbreSettings) -> SynthesisResult:
        if _DIGITS.search(text):
            raise ValueError("Timbre text must write numbers as words, not digits")
        key = self.cache_key(text, settings)
        if self._cache is not None and (hit := self._cache.get(key)) is not None:
            return SynthesisResult(hit.value, hit.latency_ms, cached=True)

        payload = {
            "text": text,
            "model": settings.model,
            "voice": settings.voice,
            "language": settings.language,
            "audio_config": {"sample_rate": settings.sample_rate, "container": settings.container},
        }
        resp, latency_ms = post_with_retry(
            self._http,
            self._url,
            name="timbre",
            sleep=self._sleep,
            throttle=self._throttle,
            headers={"X-API-Key-ID": self._key},
            json=payload,
        )
        audio = resp.content
        if not _looks_like_audio(audio, settings.container):
            raise ApiError("timbre: response is not audio", resp.status_code)
        if self._cache is not None:
            self._cache.put(key, "timbre", settings.as_dict(), audio, latency_ms)
        return SynthesisResult(audio, latency_ms, cached=False)
