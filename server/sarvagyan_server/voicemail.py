"""Translated voicemail.

    sender records (their language, e.g. Tamil or Tamil-English mix)
      -> POST /v1/voicemails: raw 16 kHz PCM, held in memory only
      -> Prisma streaming STT (real-time cadence, as the protocol requires) -> audio discarded
      -> MyMemory translation to the recipient's preferred language
      -> stored as text only (original + translation), kept at most RETENTION_S
    recipient presses play
      -> GET /v1/voicemails/{id}/audio: Timbre TTS generated fresh and streamed, never stored

No audio is ever written anywhere. Logs carry ids, durations and status only.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from sarvagyan_server.languages import BY_CODE, voice_for
from sarvagyan_server.providers.base import ProviderError, SpeechRecognizer, SpeechSynthesizer, Translator
from sarvagyan_server.providers.mymemory import split_for_limit

log = logging.getLogger("sarvagyan.voicemail")

SAMPLE_RATE = 16000
FRAME_BYTES = 1024
FRAME_S = FRAME_BYTES / 2 / SAMPLE_RATE  # 32 ms
MIN_BYTES = SAMPLE_RATE * 2 // 2  # 0.5 s
MAX_SECONDS = 60
MAX_BYTES = SAMPLE_RATE * 2 * MAX_SECONDS
TAIL_SILENCE_S = 1.0  # lets the recogniser's VAD close the last segment
SETTLE_S = 2.5  # after commit: wait this long without pending segments
FINAL_TIMEOUT_S = 15.0
TRANSLATE_TIMEOUT_S = 20.0
RETENTION_S = 7 * 24 * 3600
TTS_PIECE_BYTES = 300


async def transcribe(recognizer: SpeechRecognizer, pcm: bytes, language: str | None,
                     pace_s: float = FRAME_S, settle_s: float = SETTLE_S) -> tuple[str, str | None]:  # fmt: skip
    """Run a whole recording through streaming STT. Returns (text, detected language or None)."""
    session = await recognizer.open(language, SAMPLE_RATE)
    texts: list[str] = []
    detected: list[str] = []
    started = 0
    finished = 0
    last_event = time.monotonic()

    async def read() -> None:
        nonlocal started, finished, last_event
        async for ev in session.events():
            last_event = time.monotonic()
            if ev.kind == "speech_start":
                started += 1
            elif ev.kind == "transcript":
                finished += 1
                if ev.text.strip():
                    texts.append(ev.text.strip())
                if ev.language:
                    detected.append(ev.language)
            elif ev.kind == "error":
                log.warning("voicemail stt event error")

    reader = asyncio.create_task(read())
    try:
        silence = bytes(FRAME_BYTES)
        frames = [pcm[i:i + FRAME_BYTES] for i in range(0, len(pcm), FRAME_BYTES)]
        frames += [silence] * int(TAIL_SILENCE_S / FRAME_S)
        for frame in frames:
            await session.send_audio(frame)
            if pace_s:
                await asyncio.sleep(pace_s)
        await session.commit()
        deadline = time.monotonic() + FINAL_TIMEOUT_S
        while time.monotonic() < deadline and not reader.done():
            if finished >= started and time.monotonic() - last_event >= settle_s:
                break
            await asyncio.sleep(0.05)
    finally:
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await reader
        with contextlib.suppress(Exception):
            await session.close()
    return " ".join(texts).strip(), (detected[-1] if detected else None)


class VoicemailService:
    """Processes uploads in the background and streams playback. Routes only talk to this class."""

    def __init__(self, db: Any, recognizer: SpeechRecognizer, translator: Translator,
                 synthesizer_factory: Callable[[], SpeechSynthesizer], pace_s: float = FRAME_S) -> None:  # fmt: skip
        self.db = db
        self.recognizer = recognizer
        self.translator = translator
        self.synthesizer_factory = synthesizer_factory
        self.pace_s = pace_s
        self._tasks: set[asyncio.Task] = set()

    def submit(self, vm_id: str, pcm: bytes, language: str, auto_detect: bool, target: str) -> None:
        task = asyncio.create_task(self._process(vm_id, pcm, language, auto_detect, target))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _process(self, vm_id: str, pcm: bytes, language: str, auto_detect: bool, target: str) -> None:
        t0 = time.monotonic()
        try:
            text, detected = await transcribe(self.recognizer, pcm, None if auto_detect else language,
                                              self.pace_s, SETTLE_S if self.pace_s else 0.05)  # fmt: skip
            del pcm  # the recording is not needed any more
            if not text:
                self.db.finish_voicemail(vm_id, "failed", error="No speech was recognised. Please record again.")
                return
            source = detected if detected in BY_CODE else language
            if source.split("-")[0] == target.split("-")[0]:
                translation = text
            else:
                translation = await asyncio.wait_for(self.translator.translate(text, source, target), TRANSLATE_TIMEOUT_S)
            self.db.finish_voicemail(vm_id, "ready", original=text, translation=translation, source_lang=source)
            log.info("voicemail ready id=%s took_ms=%d", vm_id[:8], int((time.monotonic() - t0) * 1000))
        except TimeoutError:
            self.db.finish_voicemail(vm_id, "failed", error="Translation timed out. Please try again.")
        except ProviderError as exc:
            log.warning("voicemail failed id=%s provider=%s code=%s", vm_id[:8], exc.provider, exc.code)
            self.db.finish_voicemail(vm_id, "failed", error=exc.message)
        except Exception:
            log.exception("voicemail crashed id=%s", vm_id[:8])
            self.db.finish_voicemail(vm_id, "failed", error="Something went wrong while translating.")

    async def speech(self, text: str, language: str) -> AsyncIterator[bytes]:
        """The translated voice, generated now and streamed (raw 16 kHz PCM). Nothing is kept."""
        synth = self.synthesizer_factory()
        try:
            for piece in split_for_limit(text, TTS_PIECE_BYTES):
                async for chunk in synth.synthesize(piece, language, voice_for(language, None), 1.0, SAMPLE_RATE):
                    yield chunk
        finally:
            close = getattr(synth, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()

    async def close(self) -> None:
        for t in list(self._tasks):
            t.cancel()
