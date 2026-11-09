"""In-memory sliding-window rate limits (one server process). Keys never contain passwords or tokens."""

import time
from collections import deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, limit: int, window_s: float, now: float | None = None) -> bool:
        """Records one attempt; False when `limit` attempts already happened in the last `window_s`."""
        now = now or time.monotonic()
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(self._hits) > 50_000:  # forget idle keys so memory stays bounded
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 3600][:10_000]:
                self._hits.pop(k, None)
        return True

    def count(self, key: str, window_s: float, now: float | None = None) -> int:
        now = now or time.monotonic()
        q = self._hits.get(key)
        if not q:
            return 0
        while q and now - q[0] > window_s:
            q.popleft()
        return len(q)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
