"""Gnani Timbre realtime TTS over WebSocket (docs.gnani.ai/api/TTS/tts-websocket).

Protocol: WSS wss://api.vachana.ai/api/v1/tts with header X-API-Key-ID; send one JSON request
{text, voice, model, language, speed, audio_config}; receive {"type":"start"}, {"type":"audio",
"data":{"audio": base64}}..., then {"type":"complete"}; errors as {"type":"error","message"}.
One request at a time per connection, so each synthesizer call holds a connection lock.
We request container=raw, linear_pcm 16-bit mono so chunks can be played as they arrive.
"""

import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from sarvagyan_server.providers.base import ProviderError

log = logging.getLogger("sarvagyan.tts")
FIRST_CHUNK_TIMEOUT_S = 8.0
CHUNK_TIMEOUT_S = 6.0


class GnaniSynthesizer:
    def __init__(self, api_key: str, url: str, model: str = "timbre-v2.5") -> None:
        self._key = api_key
        self._url = url
        self._model = model
        self._ws: websockets.ClientConnection | None = None
        self._lock = asyncio.Lock()

    async def _connection(self) -> websockets.ClientConnection:
        if self._ws is not None and self._ws.state is websockets.protocol.State.OPEN:
            return self._ws
        if not self._key:
            raise ProviderError("gnani-tts", "auth", "GNANI_API_KEY is not set on the server.")
        try:
            self._ws = await websockets.connect(
                self._url, additional_headers={"X-API-Key-ID": self._key}, max_size=None, open_timeout=10
            )
        except InvalidStatus as exc:
            status = exc.response.status_code
            code = "auth" if status in (401, 403) else "rate_limited" if status == 429 else "server"
            raise ProviderError("gnani-tts", code, f"Gnani TTS refused the connection ({status}).") from None
        except (OSError, TimeoutError, websockets.exceptions.WebSocketException):
            raise ProviderError("gnani-tts", "network", "Could not reach Gnani TTS.") from None
        return self._ws

    async def synthesize(
        self, text: str, language: str, voice: str, speed: float, sample_rate: int = 16000
    ) -> AsyncIterator[bytes]:
        request = {
            "text": text,
            "voice": voice,
            "model": self._model,
            "language": language,
            "speed": speed,
            "audio_config": {"sample_rate": sample_rate, "num_channels": 1, "sample_width": 2,
                             "encoding": "linear_pcm", "container": "raw"},  # fmt: skip
        }
        async with self._lock:
            for attempt in range(2):  # a reused connection may have been closed by the server
                ws = await self._connection()
                try:
                    await ws.send(json.dumps(request))
                    break
                except ConnectionClosed:
                    self._ws = None
                    if attempt:
                        raise ProviderError("gnani-tts", "network", "TTS connection closed") from None
            # Gnani sends a stray extra `complete` after each request (seen live, 29 Oct 2026), so on a
            # reused connection we ignore everything until the `start` of THIS request.
            started = False
            got_audio = False
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), CHUNK_TIMEOUT_S if got_audio else FIRST_CHUNK_TIMEOUT_S)
                except TimeoutError:
                    self._ws = None
                    await ws.close()
                    raise ProviderError("gnani-tts", "timeout", "Speech synthesis timed out.") from None
                except ConnectionClosed:
                    self._ws = None
                    raise ProviderError("gnani-tts", "network", "TTS connection closed mid-stream") from None
                if not isinstance(raw, str):
                    continue
                msg = json.loads(raw)
                kind = msg.get("type")
                if kind == "error":
                    raise ProviderError("gnani-tts", "bad_request", str(msg.get("message", "TTS error")))
                if kind == "start":
                    started = True
                    continue
                if not started:
                    continue  # leftover from the previous request
                if kind == "audio":
                    chunk = base64.b64decode((msg.get("data") or {}).get("audio") or "")
                    if chunk:
                        got_audio = True
                        yield chunk
                elif kind == "complete":
                    if not got_audio:
                        raise ProviderError("gnani-tts", "server", "Speech synthesis returned no audio.")
                    return

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
