"""SQLite cache for Prisma/Timbre calls, keyed by sha256(content) + settings.

Only successful results are stored. A cached entry keeps the latency of the original call,
so benchmark latency numbers never include cache hits as "fast" calls.
"""

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    key        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    settings   TEXT NOT NULL,
    value      BLOB NOT NULL,
    latency_ms REAL NOT NULL,
    created_at REAL NOT NULL
)
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def settings_json(settings: dict[str, Any]) -> str:
    return json.dumps(settings, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def make_key(kind: str, content: bytes, settings: dict[str, Any]) -> str:
    """Stable key: kind + sha256(audio or text bytes) + canonical settings JSON."""
    return sha256(f"{kind}|{sha256(content)}|{settings_json(settings)}".encode())


@dataclass(frozen=True)
class CacheEntry:
    value: bytes
    latency_ms: float
    created_at: float


class Cache:
    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # Streamlit runs sessions on threads
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            row = self._db.execute(
                "SELECT value, latency_ms, created_at FROM calls WHERE key = ?", (key,)
            ).fetchone()
        return CacheEntry(bytes(row[0]), row[1], row[2]) if row else None

    def has(self, key: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM calls WHERE key = ?", (key,)).fetchone() is not None

    def put(
        self, key: str, kind: str, settings: dict[str, Any], value: bytes, latency_ms: float
    ) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO calls VALUES (?, ?, ?, ?, ?, ?)",
                (key, kind, settings_json(settings), value, latency_ms, time.time()),
            )
            self._db.commit()

    def count(self, kind: str | None = None) -> int:
        with self._lock:
            if kind is None:
                return self._db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            return self._db.execute("SELECT COUNT(*) FROM calls WHERE kind = ?", (kind,)).fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._db.close()
