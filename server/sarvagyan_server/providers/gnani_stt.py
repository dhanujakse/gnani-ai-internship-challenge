"""Gnani Prisma realtime STT over WebSocket (docs.gnani.ai/api/STT/stt-websocket).

Protocol (verified against the docs and a live probe on 29 Oct 2026):
- WSS wss://api.vachana.ai/stt/v3/stream, config in upgrade headers (x-api-key-id, language_code, model,
  x-sample-rate, VAD headers, x-idle-timeout-sec)
- send raw PCM s16le mono, exactly 1,024-byte frames at real-time cadence (32 ms at 16 kHz)
- receive JSON: connected, speech_start, processing, transcript (final per VAD segment), error
- {"type": "update_settings", "language_code": ...} changes language mid-session; {"type": "commit"} closes
  the open utterance; sessions are capped at 15 minutes (close 1001); bad key = HTTP 401 at handshake.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from sarvagyan_server.providers.base import ProviderError, SttEvent

log = logging.getLogger("sarvagyan.stt")

FRAME_BYTES = 1024
_END = object()


def _status_error(status: int) -> ProviderError:
    if status == 401:
        return ProviderError("gnani-stt", "auth", "Gnani rejected the API key (401). Check GNANI_API_KEY.")
    if status == 403:
        return ProviderError("gnani-stt", "auth", "This Gnani key is not allowed to use streaming STT (403).")
    if status == 429:
        return ProviderError("gnani-stt", "rate_limited", "Gnani streaming rate limit reached (429).")
    if status >= 500:
        return ProviderError("gnani-stt", "server", f"Gnani STT server error ({status}).")
    return ProviderError("gnani-stt", "bad_request", f"Gnani STT refused the connection ({status}).")


class GnaniSttSession:
    def __init__(self, ws: websockets.ClientConnection) -> None:
        self._ws = ws
        self._events: asyncio.Queue = asyncio.Queue()
        self._reader = asyncio.create_task(self._read())
        self._buffer = bytearray()

    async def _read(self) -> None:
        try:
            async for raw in self._ws:
                if not isinstance(raw, str):
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = msg.get("type")
                if kind == "transcript":
                    await self._events.put(SttEvent(
                        "transcript", text=(msg.get("text") or "").strip(),
                        language=msg.get("detected_language_code"), latency_ms=msg.get("latency"),
                        segment_index=msg.get("segment_index"),
                        audio_ms=int(msg["audio_duration_ms"]) if msg.get("audio_duration_ms") is not None else None,
                    ))  # fmt: skip
                elif kind in ("speech_start", "processing", "connected"):
                    await self._events.put(SttEvent("ready" if kind == "connected" else kind))
                elif kind == "error":
                    await self._events.put(SttEvent("error", message=str(msg.get("message", "STT error"))))
        except ConnectionClosed as exc:
            code = exc.rcvd.code if exc.rcvd else None
            log.info("stt closed code=%s", code)
        finally:
            await self._events.put(_END)

    async def send_audio(self, frame: bytes) -> None:
        # Re-frame to exactly 1,024 bytes as the protocol requires.
        self._buffer.extend(frame)
        try:
            while len(self._buffer) >= FRAME_BYTES:
                chunk = bytes(self._buffer[:FRAME_BYTES])
                del self._buffer[:FRAME_BYTES]
                await self._ws.send(chunk)
        except ConnectionClosed:
            raise ProviderError("gnani-stt", "closed", "STT stream closed") from None

    async def update_language(self, language: str | None) -> None:
        await self._ws.send(json.dumps({"type": "update_settings", "language_code": language or "indic-auto"}))

    async def commit(self) -> None:
        try:
            await self._ws.send(json.dumps({"type": "commit"}))
        except ConnectionClosed:
            pass

    async def events(self) -> AsyncIterator[SttEvent]:
        while True:
            ev = await self._events.get()
            if ev is _END:
                return
            yield ev

    async def close(self) -> None:
        self._reader.cancel()
        await self._ws.close()


class GnaniRecognizer:
    def __init__(self, api_key: str, url: str, model: str = "prisma-v3.0", min_silence_ms: int = 600) -> None:
        self._key = api_key
        self._url = url
        self._model = model
        self._min_silence_ms = min_silence_ms

    async def open(self, language: str | None, sample_rate: int = 16000) -> GnaniSttSession:
        if not self._key:
            raise ProviderError("gnani-stt", "auth", "GNANI_API_KEY is not set on the server.")
        headers = {
            "x-api-key-id": self._key,
            "model": self._model,
            "language_code": language or "indic-auto",
            "x-sample-rate": str(sample_rate),
            "format": "transcribe",
            "x-vad-threshold": "0.6",
            "x-min-silence-ms": str(self._min_silence_ms),
            "x-min-speech-ms": "150",
            "x-max-speech-s": "20",  # keep subtitles flowing during long monologues
            "x-idle-timeout-sec": "900",
        }
        try:
            ws = await websockets.connect(self._url, additional_headers=headers, max_size=None, open_timeout=10)
        except InvalidStatus as exc:
            raise _status_error(exc.response.status_code) from None
        except (OSError, TimeoutError, websockets.exceptions.WebSocketException):
            raise ProviderError("gnani-stt", "network", "Could not reach Gnani streaming STT.") from None
        session = GnaniSttSession(ws)
        # first event must be `connected`; an `error` here means a bad header (e.g. language)
        first = await anext(session.events(), None)
        if first is None or first.kind == "error":
            await session.close()
            msg = first.message if first else "STT stream closed during setup"
            code = "unsupported_language" if first and "language" in first.message.lower() else "bad_request"
            raise ProviderError("gnani-stt", code, msg)
        return session
