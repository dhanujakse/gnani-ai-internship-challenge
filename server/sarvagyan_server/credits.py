"""Spending the paid speech APIs carefully.

- Meter: counts what each user and the whole server sent to the paid APIs today (seconds of audio to speech
  recognition, characters to voice generation, characters to translation), and answers budget questions.
- SilenceGate: decides which microphone frames are worth sending to speech recognition. Silence (and the zeroed
  frames the app sends while a translation plays) is held back; speech goes out with a short lead-in so the first
  word isn't cut, and a short tail so the recogniser can tell the sentence ended.
- TtsCache: keeps generated audio for short, often-repeated phrases ("Hello", "Okay"), so they are paid for once.

Nothing here stores conversation content on disk; the voice cache lives in memory only and is bounded.
"""

from __future__ import annotations

import math
import struct
import threading
from collections import OrderedDict, defaultdict, deque
from datetime import date

FRAME_S = 1024 / 2 / 16000  # one 1,024-byte frame of 16 kHz s16le audio = 32 ms


class Meter:
    """Today's usage per user and for the whole server. In memory: resets when the server restarts."""

    KINDS = ("stt_s", "tts_chars", "mt_chars", "tts_cached_chars", "stt_skipped_s")

    def __init__(self, settings) -> None:
        self.s = settings
        self._lock = threading.Lock()
        self._user: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: dict.fromkeys(self.KINDS, 0.0))
        self._server: dict[str, dict[str, float]] = defaultdict(lambda: dict.fromkeys(self.KINDS, 0.0))

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    def add(self, user_id: str, kind: str, amount: float) -> None:
        if amount <= 0:
            return
        day = self._today()
        with self._lock:
            self._user[(user_id, day)][kind] += amount
            self._server[day][kind] += amount
            if len(self._server) > 3:  # keep only the last few days
                for d in sorted(self._server)[:-3]:
                    self._server.pop(d, None)
                for k in [k for k in self._user if k[1] not in self._server]:
                    self._user.pop(k, None)

    def user(self, user_id: str) -> dict[str, float]:
        return dict(self._user.get((user_id, self._today()), dict.fromkeys(self.KINDS, 0.0)))

    def server(self) -> dict[str, float]:
        return dict(self._server.get(self._today(), dict.fromkeys(self.KINDS, 0.0)))

    # budgets (0 = no limit) ------------------------------------------------------------
    def stt_allowed(self, user_id: str) -> bool:
        u, srv = self.user(user_id), self.server()
        if self.s.daily_stt_minutes_per_user and u["stt_s"] >= self.s.daily_stt_minutes_per_user * 60:
            return False
        return not (self.s.daily_server_stt_minutes and srv["stt_s"] >= self.s.daily_server_stt_minutes * 60)

    def tts_allowed(self, user_id: str, chars: int) -> bool:
        u, srv = self.user(user_id), self.server()
        if self.s.daily_tts_chars_per_user and u["tts_chars"] + chars > self.s.daily_tts_chars_per_user:
            return False
        return not (self.s.daily_server_tts_chars and srv["tts_chars"] + chars > self.s.daily_server_tts_chars)

    def report(self) -> dict:
        day = self._today()
        with self._lock:
            users = {uid: {k: round(v, 1) for k, v in vals.items()} for (uid, d), vals in self._user.items() if d == day}
        srv = self.server()
        total_audio = srv["stt_s"] + srv["stt_skipped_s"]
        return {
            "day": day,
            "server": {k: round(v, 1) for k, v in srv.items()},
            "stt_minutes": round(srv["stt_s"] / 60, 2),
            "silence_saved_pct": round(100 * srv["stt_skipped_s"] / total_audio, 1) if total_audio else 0.0,
            "tts_cache_saved_pct": round(100 * srv["tts_cached_chars"] / (srv["tts_chars"] + srv["tts_cached_chars"]), 1)
            if srv["tts_chars"] + srv["tts_cached_chars"] else 0.0,
            "users": {uid[:8]: vals for uid, vals in sorted(users.items())},  # short ids only
        }


def frame_rms(frame: bytes) -> float:
    n = len(frame) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", frame[: n * 2])
    return math.sqrt(sum(s * s for s in samples) / n)


class SilenceGate:
    """Per speaker: which mic frames go to speech recognition.

    idle  -> a frame louder than the threshold opens the gate; the held lead-in (pre-roll) goes first
    open  -> every frame goes out; after `hangover` quiet frames in a row the gate closes again
    The threshold follows the room's noise: max(min_rms, noise floor x ratio). All-zero frames (the app's echo gate
    while a translation plays) count as silence and never open the gate.
    """

    def __init__(self, preroll: int = 10, hangover: int = 25, min_rms: float = 320.0, ratio: float = 3.0) -> None:
        self.pre: deque[bytes] = deque(maxlen=preroll)
        self.hangover = hangover
        self.min_rms = min_rms
        self.ratio = ratio
        self.floor = min_rms / ratio
        self.open = False
        self.quiet = 0
        self.skipped = 0  # frames held back (never sent)

    def threshold(self) -> float:
        return max(self.min_rms, self.floor * self.ratio)

    def push(self, frame: bytes) -> list[bytes]:
        rms = frame_rms(frame)
        loud = rms > self.threshold()
        if rms > 0:  # noise floor: falls quickly to quiet frames, rises very slowly, so a steady hum stops
            # counting as speech within a few seconds while a sentence barely moves it (zero frames are ignored)
            self.floor = 0.9 * self.floor + 0.1 * rms if rms < self.floor else 0.998 * self.floor + 0.002 * rms
        if self.open:
            self.quiet = 0 if loud else self.quiet + 1
            if self.quiet >= self.hangover:
                self.open = False
                self.quiet = 0
            return [frame]
        if loud:
            self.open = True
            self.quiet = 0
            out = [*self.pre, frame]
            self.pre.clear()
            return out
        if len(self.pre) == self.pre.maxlen:
            self.skipped += 1  # the oldest held frame falls out without being sent
        self.pre.append(frame)
        return []


class TtsCache:
    """Generated audio for short phrases, keyed by (text, language, voice, speed). Memory only, LRU, bounded."""

    MAX_TEXT = 60  # only short phrases repeat often enough to be worth keeping

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self._d: OrderedDict[tuple, list[bytes]] = OrderedDict()
        self._size = 0

    @staticmethod
    def key(text: str, language: str, voice: str, speed: float) -> tuple:
        return (" ".join(text.lower().split()), language, voice, round(speed, 2))

    def cacheable(self, text: str) -> bool:
        return self.max_bytes > 0 and 0 < len(text) <= self.MAX_TEXT

    def get(self, key: tuple) -> list[bytes] | None:
        chunks = self._d.get(key)
        if chunks is not None:
            self._d.move_to_end(key)
        return chunks

    def put(self, key: tuple, chunks: list[bytes]) -> None:
        size = sum(len(c) for c in chunks)
        if size == 0 or size > self.max_bytes // 4 or key in self._d:
            return
        self._d[key] = chunks
        self._size += size
        while self._size > self.max_bytes and self._d:
            _, old = self._d.popitem(last=False)
            self._size -= sum(len(c) for c in old)
