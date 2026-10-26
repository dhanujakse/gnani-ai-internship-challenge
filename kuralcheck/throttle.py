"""Shared pacing for paid API calls: at most N calls per second across all threads.
Gnani returns 429 when calls come too fast, so every Prisma/Timbre attempt waits its turn here."""

import threading
import time
from collections.abc import Callable
from functools import lru_cache


class Throttle:
    def __init__(
        self,
        per_second: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if per_second <= 0:
            raise ValueError("per_second must be > 0")
        self.interval = 1.0 / per_second
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self.interval
        if start > now:
            self._sleep(start - now)


@lru_cache(maxsize=None)
def shared_throttle(per_second: float) -> Throttle | None:
    """One throttle per rate for the whole process, so Prisma and Timbre share the budget."""
    return Throttle(per_second) if per_second > 0 else None
