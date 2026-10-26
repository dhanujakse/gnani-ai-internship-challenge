"""Gnani Prisma speech-to-text (REST, POST /stt/v3), cached, with one retry and latency."""

import io
import json
import time
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
import soundfile as sf

from kuralcheck.cache import Cache, make_key
from kuralcheck.clients._http import post_with_retry
from kuralcheck.clients.errors import ApiError
from kuralcheck.config import Settings, get_settings
from kuralcheck.throttle import Throttle, shared_throttle

ENDPOINT = "/stt/v3"
MAX_SECONDS = 60.0
MAX_BIAS_WORDS = 100
BIAS_SCORES = (0.0, 0.5, 1.0, 1.5, 2.0)
TIMEOUT_S = 20.0
MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg", "flac": "audio/flac",
        "aac": "audio/aac", "m4a": "audio/mp4"}  # fmt: skip


def _is_word(word: str) -> bool:
    # Letters plus combining marks (Tamil vowel signs and pulli are category M*).
    return bool(word) and unicodedata.category(word[0])[0] == "L" and all(
        unicodedata.category(ch)[0] in "LM" for ch in word
    )


def validate_bias_list(words: Sequence[str]) -> list[str]:
    """Prisma silently ignores an invalid bias_list, so check it here and fail loudly."""
    words = [unicodedata.normalize("NFC", w) for w in words]
    if len(words) > MAX_BIAS_WORDS:
        raise ValueError(f"bias_list has {len(words)} words; Prisma allows at most {MAX_BIAS_WORDS}")
    bad = [w for w in words if not _is_word(w)]
    if bad:
        raise ValueError(f"bias_list must be single words, letters only; invalid: {bad[:5]}")
    return words


@dataclass(frozen=True)
class PrismaSettings:
    format: Literal["verbatim", "transcribe"] = "verbatim"
    bias_list: tuple[str, ...] = field(default=())
    bias_score: float | None = None
    language_code: str = "ta-IN"

    def __post_init__(self) -> None:
        if self.bias_score is not None and self.bias_score not in BIAS_SCORES:
            raise ValueError(f"bias_score must be one of {BIAS_SCORES}")
        object.__setattr__(self, "bias_list", tuple(validate_bias_list(self.bias_list)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint": ENDPOINT,
            "language_code": self.language_code,
            "format": self.format,
            "bias_list": list(self.bias_list),
            "bias_score": self.bias_score if self.bias_list else None,
        }


@dataclass(frozen=True)
class TranscriptResult:
    transcript: str
    latency_ms: float  # of the original (uncached) call
    cached: bool


def audio_seconds(audio: bytes) -> float | None:
    """Duration for formats soundfile can read (WAV/FLAC/OGG); None otherwise."""
    try:
        info = sf.info(io.BytesIO(audio))
    except Exception:
        return None
    return info.frames / info.samplerate


class PrismaClient:
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
    def from_settings(cls, settings: Settings | None = None, cache: Cache | None = None) -> "PrismaClient":
        s = settings or get_settings()
        return cls(s.gnani_api_key.get_secret_value(), cache or Cache(s.cache_path), s.gnani_base_url,
                   throttle=shared_throttle(s.gnani_calls_per_second))

    def cache_key(self, audio: bytes, settings: PrismaSettings) -> str:
        return make_key("prisma", audio, settings.as_dict())

    def is_cached(self, audio: bytes, settings: PrismaSettings) -> bool:
        return self._cache is not None and self._cache.has(self.cache_key(audio, settings))

    def transcribe(self, audio: bytes, filename: str, settings: PrismaSettings) -> TranscriptResult:
        key = self.cache_key(audio, settings)
        if self._cache is not None and (hit := self._cache.get(key)) is not None:
            return TranscriptResult(hit.value.decode("utf-8"), hit.latency_ms, cached=True)

        seconds = audio_seconds(audio)
        if seconds is not None and seconds > MAX_SECONDS:
            raise ValueError(f"audio is {seconds:.1f} s; Prisma accepts at most {MAX_SECONDS:.0f} s")

        ext = filename.rsplit(".", 1)[-1].lower()
        data: dict[str, str] = {"language_code": settings.language_code, "format": settings.format}
        if settings.bias_list:
            data["bias_list"] = json.dumps(list(settings.bias_list), ensure_ascii=False)
            if settings.bias_score is not None:
                data["bias_score"] = str(settings.bias_score)

        resp, latency_ms = post_with_retry(
            self._http,
            self._url,
            name="prisma",
            sleep=self._sleep,
            throttle=self._throttle,
            headers={"X-API-Key-ID": self._key},
            data=data,
            files={"audio_file": (filename, audio, MIME.get(ext, "application/octet-stream"))},
        )
        try:
            body = resp.json()
        except ValueError:
            raise ApiError("prisma: response is not JSON", resp.status_code) from None
        if body.get("success") is False or not isinstance(body.get("transcript"), str):
            raise ApiError("prisma: unsuccessful response", resp.status_code)

        transcript: str = body["transcript"]
        if self._cache is not None:
            self._cache.put(key, "prisma", settings.as_dict(), transcript.encode("utf-8"), latency_ms)
        return TranscriptResult(transcript, latency_ms, cached=False)
