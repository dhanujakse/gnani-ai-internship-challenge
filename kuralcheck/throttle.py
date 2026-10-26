"""Adaptive pacing for paid API calls, shared by all threads (AIMD, like TCP congestion control).

Every Prisma/Timbre attempt waits its turn here. Each success nudges the rate up a little
(additive increase); a 429 halves it (multiplicative decrease). Runs converge on the fastest
rate Gnani accepts, so we get good throughput without spending retries on 429s.
"""

import threading
import time
from collections.abc import Callable
from functools import lru_cache


class Throttle:
    def __init__(
        self,
        per_second: float,
        max_per_second: float | None = None,
        min_per_second: float = 0.2,
        step: float = 0.05,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if per_second <= 0:
            raise ValueError("per_second must be > 0")
        self.rate = per_second
        self.max_rate = max_per_second or per_second  # equal to start rate = fixed pacing
        self.min_rate = min(min_per_second, per_second)
        self.step = step
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next = 0.0
        self.rate_limited = 0

    @property
    def interval(self) -> float:
        return 1.0 / self.rate

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + 1.0 / self.rate
        if start > now:
            self._sleep(start - now)

    def on_success(self) -> None:
        with self._lock:
            self.rate = min(self.max_rate, self.rate + self.step)

    def on_rate_limited(self) -> None:
        with self._lock:
            self.rate = max(self.min_rate, self.rate / 2)
            self.rate_limited += 1
            self._next = self._clock() + 1.0 / self.rate  # pause the whole pool briefly


@lru_cache(maxsize=None)
def shared_throttle(per_second: float, max_per_second: float | None = None) -> Throttle | None:
    """One throttle per setting for the whole process, so Prisma and Timbre share the budget."""
    return Throttle(per_second, max_per_second) if per_second > 0 else None
