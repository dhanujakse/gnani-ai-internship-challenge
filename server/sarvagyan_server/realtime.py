"""Real-time call rooms and the translation pipeline.

Per call there is one CallRoom with up to two Participants. For each participant:

    mic PCM (client WS, binary) -> SpeakerPipeline -> Prisma streaming STT (their language)
        -> final transcript -> Translator (to the peer's language)
        -> PlaybackDispatcher of the PEER -> Timbre streaming TTS -> peer's WS (binary PCM)

The original voices travel peer-to-peer over WebRTC; this server only relays signalling.
Translated audio goes only to the listener, never back to the speaker, and an EchoGuard drops
transcripts that match translated speech the listener just heard (mic pickup), so translated
speech is never re-translated. Every utterance has an id and a stage that only moves forward,
so late responses never overwrite newer turns and clients can upsert without duplicates.
"""

import asyncio
import contextlib
import logging
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from sarvagyan_server.languages import clamp_speed, get_language, voice_for
from sarvagyan_server.credits import FRAME_S, Meter, SilenceGate, TtsCache
from sarvagyan_server.providers.base import ProviderError, SpeechRecognizer, SpeechSynthesizer, Translator

log = logging.getLogger("sarvagyan.realtime")

SAMPLE_RATE = 16000
TRANSLATE_TIMEOUT_S = 8.0
MAX_AUDIO_AGE_S = 12.0  # translated audio older than this is skipped (text still shown)
ECHO_WINDOW_S = 20.0
ECHO_SIMILARITY = 0.72
STT_ROTATE_S = 14 * 60  # Gnani sessions are capped at 15 min; rotate proactively
GRACE_S = 30.0  # keep a dropped participant's seat this long (network blips)
FRAME_QUEUE = 160  # ~5 s of 32 ms frames
STAGES = ("listening", "recognized", "translating", "translated", "speaking", "done", "failed", "skipped")
STAGE_RANK = {s: i for i, s in enumerate(STAGES)}

Send = Callable[[dict | bytes], Awaitable[None]]


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.lower()).strip()


class EchoGuard:
    """Remembers translated speech played to one participant, to reject it if their mic picks it up."""

    def __init__(self, window_s: float = ECHO_WINDOW_S, threshold: float = ECHO_SIMILARITY) -> None:
        self._recent: deque[tuple[float, str]] = deque(maxlen=20)
        self._window = window_s
        self._threshold = threshold
        self.blocked = 0

    def register(self, text: str, now: float | None = None) -> None:
        if text.strip():
            self._recent.append(((now or time.monotonic()), _norm(text)))

    def is_echo(self, text: str, now: float | None = None) -> bool:
        now = now or time.monotonic()
        heard = _norm(text)
        if not heard:
            return False
        for t, played in self._recent:
            if now - t > self._window:
                continue
            if heard == played or (len(heard) > 8 and (heard in played or played in heard)) or \
                    SequenceMatcher(None, heard, played).ratio() >= self._threshold:  # fmt: skip
                self.blocked += 1
                return True
        return False


@dataclass
class Utterance:
    id: str
    speaker_id: str
    seq: int
    original: str
    source_lang: str
    t_final: float
    target_lang: str | None = None
    translation: str | None = None
    stage: str = "recognized"
    error: str | None = None
    rev: int = 0
    metrics: dict[str, int] = field(default_factory=dict)

    def event(self) -> dict:
        return {"type": "utterance", "id": self.id, "speaker_id": self.speaker_id, "seq": self.seq,
                "stage": self.stage, "rev": self.rev, "original": self.original, "source_lang": self.source_lang,
                "translation": self.translation, "target_lang": self.target_lang, "error": self.error,
                "metrics": dict(self.metrics)}  # fmt: skip


@dataclass
class Participant:
    user_id: str
    name: str
    language: str = "ta-IN"
    auto_detect: bool = False
    voice: str | None = None
    speed: float = 1.0
    translate_audio: bool = True  # hear translated speech (subtitles always on)
    muted: bool = False
    send: Send | None = None
    connected: bool = False
    echo: EchoGuard = field(default_factory=EchoGuard)
    joined_order: int = 0

    def public(self) -> dict:
        return {"user_id": self.user_id, "name": self.name, "language": self.language,
                "auto_detect": self.auto_detect, "muted": self.muted, "connected": self.connected}  # fmt: skip

    def apply(self, cfg: dict) -> None:
        if "language" in cfg:
            get_language(cfg["language"])  # raises ValueError if unsupported
            self.language = cfg["language"]
        if "auto_detect" in cfg:
            self.auto_detect = bool(cfg["auto_detect"])
        if "voice" in cfg:
            self.voice = cfg["voice"]
        if "speed" in cfg:
            self.speed = clamp_speed(cfg["speed"])
        if "translate_audio" in cfg:
            self.translate_audio = bool(cfg["translate_audio"])
        if "muted" in cfg:
            self.muted = bool(cfg["muted"])


class Outbox:
    """Single writer per WebSocket: events and audio are sent in order, never concurrently."""

    def __init__(self, send: Send) -> None:
        self._send = send
        self._q: asyncio.Queue = asyncio.Queue(maxsize=4000)
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            item = await self._q.get()
            try:
                await self._send(item)
            except Exception:  # socket gone; the room handles the disconnect
                return

    async def put(self, item: dict | bytes) -> None:
        if self._q.full():
            return  # client is not reading; drop rather than grow without bound
        await self._q.put(item)

    async def close(self) -> None:
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task


class SpeakerPipeline:
    """Mic frames of one participant -> streaming STT -> translation -> peer's playback queue."""

    def __init__(self, room: "CallRoom", speaker: Participant) -> None:
        self.room = room
        self.speaker = speaker
        self.tag = "a" if speaker.joined_order == 0 else "b"
        self._frames: asyncio.Queue[bytes] = asyncio.Queue(maxsize=FRAME_QUEUE)
        self._task: asyncio.Task | None = None
        self._session: Any = None
        self._tasks: set[asyncio.Task] = set()
        self._stopped = False
        self._seq = 0
        self._in_speech = False
        self._last_transcript = ""
        self._last_transcript_time = 0.0
        # credits: only speech goes to recognition; the stream closes after a long silence and reopens on speech
        self._gate = SilenceGate() if room.gate_enabled else None
        self._wake = asyncio.Event()
        self._idle_closed = False
        self._budget_noticed = False

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def feed(self, frame: bytes) -> None:
        if self.speaker.muted or self._stopped:
            return
        if self._gate is not None:
            before = self._gate.skipped
            frames = self._gate.push(frame)
            if self._gate.skipped > before:
                self.room.meter_add(self.speaker.user_id, "stt_skipped_s", FRAME_S)
        else:
            frames = [frame]
        for f in frames:
            if self._frames.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._frames.get_nowait()  # drop oldest: stay real-time
            self._frames.put_nowait(f)
        if frames:
            self._wake.set()

    async def set_language(self) -> None:
        if self._session is not None:
            with contextlib.suppress(Exception):
                await self._session.update_language(None if self.speaker.auto_detect else self.speaker.language)

    async def stop(self) -> None:
        self._stopped = True
        for t in list(self._tasks):
            t.cancel()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        if self._session is not None:
            with contextlib.suppress(Exception):
                await self._session.close()

    async def _status(self, state: str, message: str = "") -> None:
        await self.room.broadcast({"type": "pipeline", "speaker_id": self.speaker.user_id, "stt": state, "message": message})

    async def _pump(self, session: Any) -> None:
        uid = self.speaker.user_id
        while True:
            try:
                frame = await asyncio.wait_for(self._frames.get(), self.room.idle_close_s if self.room.idle_close_s > 0 else None)
            except TimeoutError:
                if self._in_speech:
                    continue
                # a long silence: close the paid stream; _run reopens it when speech comes back
                self._idle_closed = True
                log.info("stt idle close speaker=%s", uid[:8])
                with contextlib.suppress(Exception):
                    await session.close()
                return
            if not self.room.stt_allowed(uid):
                if not self._budget_noticed:
                    self._budget_noticed = True
                    await self.room.error(self.speaker, "stt", ProviderError(
                        "server", "quota", "Daily speech limit reached for this account. Subtitles pause until tomorrow."))
                continue
            await session.send_audio(frame)
            self.room.meter_add(uid, "stt_s", len(frame) / 2 / SAMPLE_RATE)

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stopped:
            pump: asyncio.Task | None = None
            quiet = self._idle_closed  # reopening after a silence: the user saw no outage, so no status change
            if quiet:  # wait for speech, then reopen
                self._wake.clear()
                if self._frames.empty():
                    await self._wake.wait()
                self._idle_closed = False
            try:
                if not quiet:
                    await self._status("connecting")
                lang = None if self.speaker.auto_detect else self.speaker.language
                self._session = await self.room.recognizer.open(lang, SAMPLE_RATE)
                if not quiet:
                    await self._status("ready")
                backoff = 1.0
                opened = time.monotonic()
                pump = asyncio.create_task(self._pump(self._session))
                async for ev in self._session.events():
                    await self._on_event(ev)
                    if time.monotonic() - opened > STT_ROTATE_S and not self._in_speech:
                        break  # rotate before the 15-minute cap, between utterances
                    if pump.done():
                        break
            except asyncio.CancelledError:
                raise
            except ProviderError as exc:
                await self.room.error(self.speaker, "stt", exc)
                if exc.code in ("auth", "unsupported_language", "bad_request", "quota"):
                    await self._status("error", exc.message)
                    return  # will not heal by retrying; settings change restarts the pipeline
            except Exception:
                log.exception("stt pipeline crashed speaker=%s", self.speaker.user_id[:8])
            finally:
                if pump is not None:
                    pump.cancel()
                if self._session is not None:
                    with contextlib.suppress(Exception):
                        await self._session.close()
                    self._session = None
            if self._stopped:
                return
            if self._idle_closed:
                continue
            await self._status("reconnecting")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15.0)

    async def _on_event(self, ev: Any) -> None:
        if ev.kind == "speech_start":
            self._in_speech = True
            await self.room.broadcast({"type": "speech_activity", "speaker_id": self.speaker.user_id, "active": True})
        elif ev.kind == "error":
            await self.room.error(self.speaker, "stt", ProviderError("gnani-stt", "server", ev.message), notify_peer=False)
        elif ev.kind == "transcript":
            self._in_speech = False
            await self.room.broadcast({"type": "speech_activity", "speaker_id": self.speaker.user_id, "active": False})
            text = ev.text.strip()
            if not text:
                await self.room.send(self.speaker, {"type": "notice", "code": "unclear",
                                                    "message": "Didn't catch that — please repeat."})  # fmt: skip
                return
            now = time.monotonic()
            if text == self._last_transcript and (now - self._last_transcript_time) < 1.5:
                log.info("duplicate transcript dropped speaker=%s", self.speaker.user_id[:8])
                return
            self._last_transcript = text
            self._last_transcript_time = now
            if self.speaker.echo.is_echo(text):
                log.info("echo dropped speaker=%s", self.speaker.user_id[:8])
                return
            if not self.room.allow_utterance(self.speaker.user_id):
                await self.room.error(self.speaker, "translation",
                                      ProviderError("server", "quota", "Daily translation limit reached for this account."))  # fmt: skip
                return
            self._seq += 1
            source = ev.language if ev.language in _supported() else self.speaker.language
            utt = Utterance(id=f"{self.room.call_id[:6]}-{self.tag}{self._seq}", speaker_id=self.speaker.user_id,
                            seq=self._seq, original=text, source_lang=source, t_final=time.monotonic())  # fmt: skip
            if ev.latency_ms is not None:
                utt.metrics["stt_ms"] = int(ev.latency_ms)
            if ev.audio_ms is not None:
                utt.metrics["speech_ms"] = int(ev.audio_ms)
            self.room.remember(utt)
            await self.room.update(utt, "recognized")
            task = asyncio.create_task(self.room.translate_and_dispatch(utt))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)


async def _replay(chunks: list[bytes]):
    for c in chunks:
        yield c
        await asyncio.sleep(0)


def _supported() -> set[str]:
    from sarvagyan_server.languages import BY_CODE

    return set(BY_CODE)


class PlaybackDispatcher:
    """Plays translated speech to one listener, in utterance order, one at a time."""

    def __init__(self, room: "CallRoom", listener: Participant) -> None:
        self.room = room
        self.listener = listener
        self._q: asyncio.Queue[Utterance] = asyncio.Queue()
        self._task = asyncio.create_task(self._work())

    def submit(self, utt: Utterance) -> None:
        self._q.put_nowait(utt)

    async def stop(self) -> None:
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _work(self) -> None:
        while True:
            utt = await self._q.get()
            try:
                await self._play(utt)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("playback failed utt=%s", utt.id)

    async def _play(self, utt: Utterance) -> None:
        lis = self.listener
        if not lis.translate_audio or not lis.connected or not utt.translation:
            await self.room.update(utt, "done")
            return
        if time.monotonic() - utt.t_final > MAX_AUDIO_AGE_S:
            utt.error = "Translated voice skipped (arrived too late); subtitle shown."
            await self.room.update(utt, "skipped")
            return
        target = utt.target_lang or lis.language
        voice = voice_for(target, lis.voice)
        cache, key = self.room.tts_cache, None
        cached = None
        if cache is not None and cache.cacheable(utt.translation):
            key = TtsCache.key(utt.translation, target, voice, lis.speed)
            cached = cache.get(key)
        # voice budget (per listener and server-wide): when it runs out the call carries on with subtitles only
        if cached is None and not self.room.tts_allowed(lis.user_id, len(utt.translation)):
            utt.error = "Daily translated-voice limit reached; subtitle shown."
            await self.room.update(utt, "skipped")
            return
        await self.room.update(utt, "speaking")
        await self.room.send(lis, {"type": "tts_start", "id": utt.id, "sample_rate": SAMPLE_RATE})
        t0 = time.monotonic()
        total = 0
        ok = True
        keep: list[bytes] = []
        try:
            if cached is not None:  # paid for once already
                source = _replay(cached)
                self.room.meter_add(lis.user_id, "tts_cached_chars", len(utt.translation))
                utt.metrics["tts_cached"] = 1
            else:
                source = self.room.synthesizer.synthesize(utt.translation, target, voice, lis.speed, SAMPLE_RATE)
                self.room.meter_add(lis.user_id, "tts_chars", len(utt.translation))
            async for chunk in source:
                if total == 0:
                    utt.metrics["tts_first_ms"] = int((time.monotonic() - t0) * 1000)
                    utt.metrics["server_total_ms"] = int((time.monotonic() - utt.t_final) * 1000)
                total += len(chunk)
                if key is not None and cached is None:
                    keep.append(chunk)
                await self.room.send(lis, chunk)
        except ProviderError as exc:
            ok = False
            utt.error = f"Translated voice unavailable ({exc.message}); subtitle shown."
            await self.room.error(lis, "tts", exc, notify_peer=False)
        finally:
            await self.room.send(lis, {"type": "tts_end", "id": utt.id, "ok": ok})
        if ok and key is not None and cached is None and keep:
            cache.put(key, keep)
        lis.echo.register(utt.translation)  # the listener's mic may pick this up
        utt.metrics["tts_total_ms"] = int((time.monotonic() - t0) * 1000)
        utt.metrics["audio_ms"] = int(total / 2 / SAMPLE_RATE * 1000)
        await self.room.update(utt, "done")


class CallRoom:
    def __init__(self, call_id: str, recognizer: SpeechRecognizer, translator: Translator,
                 synthesizer_factory: Callable[[], SpeechSynthesizer],
                 on_started: Callable[[str], None] | None = None, quota: Callable[[str], bool] | None = None,
                 on_empty: Callable[[], Awaitable[None]] | None = None, meter: Meter | None = None,
                 tts_cache: TtsCache | None = None, gate: bool = False, idle_close_s: float = 0.0) -> None:  # fmt: skip
        self.call_id = call_id
        self.meter = meter
        self.tts_cache = tts_cache
        self.gate_enabled = gate
        self.idle_close_s = idle_close_s
        self.recognizer = recognizer
        self.translator = translator
        self._synth_factory = synthesizer_factory
        self.synthesizer: SpeechSynthesizer = synthesizer_factory()
        self.participants: dict[str, Participant] = {}
        self.outboxes: dict[str, Outbox] = {}
        self.pipelines: dict[str, SpeakerPipeline] = {}
        self.dispatchers: dict[str, PlaybackDispatcher] = {}
        self.utterances: dict[str, Utterance] = {}
        self._grace: dict[str, asyncio.Task] = {}
        self._on_started = on_started
        self._quota = quota
        self._on_empty = on_empty
        self.started_at: float | None = None
        self.utterance_count = 0
        self.ended = False

    # participants ---------------------------------------------------------------------
    def peer_of(self, user_id: str) -> Participant | None:
        return next((p for uid, p in self.participants.items() if uid != user_id), None)

    async def connect(self, part: Participant, send: Send) -> None:
        existing = self.participants.get(part.user_id)
        if existing is not None:  # reconnect within grace: keep identity and order
            part.joined_order = existing.joined_order
            part.echo = existing.echo
            if (t := self._grace.pop(part.user_id, None)) is not None:
                t.cancel()
            await self._teardown(part.user_id)
        else:
            if len(self.participants) >= 2:
                raise PermissionError("This call already has two participants.")
            part.joined_order = len(self.participants)
        part.connected = True
        part.send = send
        self.participants[part.user_id] = part
        self.outboxes[part.user_id] = Outbox(send)
        self.dispatchers[part.user_id] = PlaybackDispatcher(self, part)
        self.pipelines[part.user_id] = SpeakerPipeline(self, part)
        peer = self.peer_of(part.user_id)
        await self.send(part, {"type": "joined", "call_id": self.call_id, "you": part.public(),
                               "peer": peer.public() if peer else None})  # fmt: skip
        if peer is not None and peer.connected:
            if self.started_at is None:
                self.started_at = time.time()
                if self._on_started:
                    self._on_started(self.call_id)
            # the participant who was there first creates the WebRTC offer
            first, second = sorted((part, peer), key=lambda p: p.joined_order)
            await self.send(first, {"type": "peer_joined", "peer": second.public(), "initiator": True})
            await self.send(second, {"type": "peer_joined", "peer": first.public(), "initiator": False})
            # speech recognition runs only while both people are connected (saves credits and sessions)
            for uid in (part.user_id, peer.user_id):
                self.pipelines[uid].start()

    async def _pause_pipeline(self, user_id: str) -> None:
        """Stop a participant's STT (nobody to translate for) and prepare a fresh, unstarted one."""
        part = self.participants.get(user_id)
        if (pipe := self.pipelines.pop(user_id, None)) is not None:
            await pipe.stop()
        if part is not None and part.connected:
            self.pipelines[user_id] = SpeakerPipeline(self, part)

    async def _teardown(self, user_id: str) -> None:
        if (pipe := self.pipelines.pop(user_id, None)) is not None:
            await pipe.stop()
        if (disp := self.dispatchers.pop(user_id, None)) is not None:
            await disp.stop()
        if (box := self.outboxes.pop(user_id, None)) is not None:
            await box.close()

    async def disconnect(self, user_id: str, leaving: bool) -> None:
        part = self.participants.get(user_id)
        if part is None:
            return
        part.connected = False
        part.send = None
        await self._teardown(user_id)
        peer = self.peer_of(user_id)
        if peer is not None:
            await self._pause_pipeline(peer.user_id)
        if leaving:
            self.participants.pop(user_id, None)
            if peer is not None:
                await self.send(peer, {"type": "peer_left", "peer_id": user_id, "reason": "left"})
        else:
            if peer is not None:
                await self.send(peer, {"type": "peer_reconnecting", "peer_id": user_id})
            self._grace[user_id] = asyncio.create_task(self._expire(user_id))

    async def _expire(self, user_id: str) -> None:
        await asyncio.sleep(GRACE_S)
        self._grace.pop(user_id, None)
        part = self.participants.get(user_id)
        if part is not None and not part.connected:
            self.participants.pop(user_id, None)
            peer = self.peer_of(user_id)
            if peer is not None:
                await self.send(peer, {"type": "peer_left", "peer_id": user_id, "reason": "connection_lost"})
        if self.is_empty() and self._on_empty is not None:
            await self._on_empty()

    def is_empty(self) -> bool:
        return not any(p.connected for p in self.participants.values()) and not self._grace

    async def close(self) -> None:
        self.ended = True
        for t in self._grace.values():
            t.cancel()
        for uid in list(self.participants):
            await self._teardown(uid)
        with contextlib.suppress(Exception):
            close = getattr(self.synthesizer, "close", None)
            if close:
                await close()

    # messaging -------------------------------------------------------------------------
    async def send(self, part: Participant, item: dict | bytes) -> None:
        box = self.outboxes.get(part.user_id)
        if box is not None and part.connected:
            await box.put(item)

    async def broadcast(self, event: dict) -> None:
        for p in list(self.participants.values()):
            await self.send(p, event)

    async def relay_signal(self, sender_id: str, payload: Any) -> bool:
        peer = self.peer_of(sender_id)
        if peer is None or not peer.connected:
            return False
        await self.send(peer, {"type": "signal", "from": sender_id, "payload": payload})
        return True

    async def error(self, part: Participant, scope: str, exc: ProviderError, notify_peer: bool = False) -> None:
        event = {"type": "error", "scope": scope, "code": exc.code, "message": exc.message,
                 "retryable": exc.retryable, "speaker_id": part.user_id}  # fmt: skip
        log.warning("provider error scope=%s code=%s call=%s", scope, exc.code, self.call_id[:8])
        if notify_peer:
            await self.broadcast(event)
        else:
            await self.send(part, event)

    # credits -------------------------------------------------------------------------------
    def meter_add(self, user_id: str, kind: str, amount: float) -> None:
        if self.meter is not None:
            self.meter.add(user_id, kind, amount)

    def stt_allowed(self, user_id: str) -> bool:
        return self.meter.stt_allowed(user_id) if self.meter is not None else True

    def tts_allowed(self, user_id: str, chars: int) -> bool:
        return self.meter.tts_allowed(user_id, chars) if self.meter is not None else True

    # utterances --------------------------------------------------------------------------
    def allow_utterance(self, user_id: str) -> bool:
        return self._quota(user_id) if self._quota else True

    def remember(self, utt: Utterance) -> None:
        self.utterances[utt.id] = utt
        self.utterance_count += 1
        if len(self.utterances) > 60:
            self.utterances.pop(next(iter(self.utterances)))

    async def update(self, utt: Utterance, stage: str) -> None:
        if STAGE_RANK[stage] < STAGE_RANK[utt.stage] and stage != "translating":
            return  # never move backwards
        utt.stage = stage
        utt.rev += 1
        await self.broadcast(utt.event())

    async def translate_and_dispatch(self, utt: Utterance) -> None:
        listener = self.peer_of(utt.speaker_id)
        if listener is None:
            utt.error = "Nobody is listening yet."
            await self.update(utt, "done")
            return
        target = listener.language
        utt.target_lang = target
        if target.split("-")[0] == utt.source_lang.split("-")[0]:
            utt.translation = utt.original  # same language: no translation or synthetic voice needed
            utt.metrics["translate_ms"] = 0
            await self.update(utt, "translated")
            await self.update(utt, "done")
            return
        await self.update(utt, "translating")
        self.meter_add(utt.speaker_id, "mt_chars", len(utt.original))
        t0 = time.monotonic()
        try:
            utt.translation = await asyncio.wait_for(
                self.translator.translate(utt.original, utt.source_lang, target), TRANSLATE_TIMEOUT_S
            )
        except TimeoutError:
            utt.error = "Translation timed out."
            await self.update(utt, "failed")
            return
        except ProviderError as exc:
            utt.error = exc.message
            await self.update(utt, "failed")
            return
        utt.metrics["translate_ms"] = int((time.monotonic() - t0) * 1000)
        if utt.metrics["translate_ms"] > 3000:
            utt.metrics["delayed"] = 1
        await self.update(utt, "translated")
        disp = self.dispatchers.get(listener.user_id)
        if disp is not None:
            disp.submit(utt)
        else:
            await self.update(utt, "done")

    async def retry(self, utt_id: str) -> bool:
        utt = self.utterances.get(utt_id)
        if utt is None or utt.stage != "failed":
            return False
        utt.error = None
        utt.stage = "recognized"
        utt.t_final = time.monotonic()
        await self.translate_and_dispatch(utt)
        return True
