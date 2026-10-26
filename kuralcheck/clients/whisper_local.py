"""Open-model baseline: Whisper small (MIT licence) run offline with faster-whisper on CPU.

Install with `uv sync --group whisper`. The model (~480 MB) downloads once on first use.
Results are cached like Prisma's (kind "whisper"), so re-runs are instant.
It plugs into runner.py through the same transcribe() interface as PrismaClient.
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Any

from kuralcheck.cache import Cache, make_key
from kuralcheck.clients.prisma import PrismaSettings, TranscriptResult

MODEL_NAME = "whisper-small"


class WhisperLocal:
    def __init__(
        self,
        cache: Cache | None,
        model_size: str = "small",
        language: str = "ta",
        model: Any = None,  # injectable for tests
    ) -> None:
        self._cache = cache
        self.model_size = model_size
        self.language = language
        self._model = model

    @property
    def name(self) -> str:
        return f"whisper-{self.model_size}"

    def _settings(self) -> dict[str, Any]:
        # greedy decoding, no timestamps, no carry-over between segments: several times faster on CPU
        # and fewer repetition loops; same settings for every condition so the comparison stays fair
        return {"model": self.name, "language": self.language, "beam_size": 1, "temperature": 0.0,
                "condition_on_previous_text": False, "without_timestamps": True}

    def _load(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise RuntimeError("faster-whisper is not installed: run `uv sync --group whisper`") from None
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8",
                                       cpu_threads=os.cpu_count() or 4)
        return self._model

    def is_cached(self, audio: bytes, settings: PrismaSettings | None = None) -> bool:
        return self._cache is not None and self._cache.has(make_key("whisper", audio, self._settings()))

    def transcribe(self, audio: bytes, filename: str, settings: PrismaSettings | None = None) -> TranscriptResult:
        key = make_key("whisper", audio, self._settings())
        if self._cache is not None and (hit := self._cache.get(key)) is not None:
            return TranscriptResult(hit.value.decode("utf-8"), hit.latency_ms, cached=True)
        model = self._load()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / (Path(filename).name or "audio.wav")
            path.write_bytes(audio)
            start = time.perf_counter()
            segments, _ = model.transcribe(
                str(path), language=self.language, beam_size=1, temperature=0.0, vad_filter=False,
                condition_on_previous_text=False, without_timestamps=True,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            latency_ms = (time.perf_counter() - start) * 1000
        if self._cache is not None:
            self._cache.put(key, "whisper", self._settings(), text.encode("utf-8"), latency_ms)
        return TranscriptResult(text, latency_ms, cached=False)

