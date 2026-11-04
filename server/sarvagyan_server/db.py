"""SQLite storage: users, call metadata, favourites and voicemail text.

No audio is ever stored. Live-call transcripts are never stored here. The only conversation text kept is a
voicemail's recognised text and its translation, so it can wait for the recipient; it is deleted when either
person deletes it, and automatically after 7 days.
"""

import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT UNIQUE, display_name TEXT NOT NULL, password_hash TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0, language TEXT NOT NULL DEFAULT 'ta-IN', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY, invite_code TEXT NOT NULL, host_id TEXT NOT NULL, status TEXT NOT NULL,
    created_at REAL NOT NULL, started_at REAL, ended_at REAL, utterances INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS calls_code ON calls(invite_code);
CREATE TABLE IF NOT EXISTS call_participants (
    call_id TEXT NOT NULL, user_id TEXT NOT NULL, language TEXT NOT NULL, joined_at REAL NOT NULL,
    PRIMARY KEY (call_id, user_id)
);
CREATE TABLE IF NOT EXISTS favourites (
    user_id TEXT NOT NULL, contact_id TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY (user_id, contact_id)
);
CREATE TABLE IF NOT EXISTS voicemails (
    id TEXT PRIMARY KEY, sender_id TEXT NOT NULL, recipient_id TEXT NOT NULL, source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL, status TEXT NOT NULL, original TEXT, translation TEXT, error TEXT,
    duration_ms INTEGER NOT NULL, created_at REAL NOT NULL, heard_at REAL
);
CREATE INDEX IF NOT EXISTS voicemails_recipient ON voicemails(recipient_id, created_at);
CREATE INDEX IF NOT EXISTS voicemails_sender ON voicemails(sender_id, created_at);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, args)
            rows = cur.fetchall()
            self._db.commit()
            return rows

    # users -----------------------------------------------------------------------
    def create_user(self, display_name: str, email: str | None, password_hash: str | None, is_demo: bool) -> dict:
        uid = uuid.uuid4().hex
        self._exec("INSERT INTO users (id, email, display_name, password_hash, is_demo, created_at) VALUES (?,?,?,?,?,?)",
                   (uid, email, display_name, password_hash, int(is_demo), time.time()))  # fmt: skip
        return self.get_user(uid)  # type: ignore[return-value]

    def get_user(self, uid: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE id = ?", (uid,))
        return dict(rows[0]) if rows else None

    def get_user_by_email(self, email: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE email = ?", (email,))
        return dict(rows[0]) if rows else None

    def update_user(self, uid: str, **fields: Any) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in ("display_name", "language") and v is not None}
        if allowed:
            sets = ", ".join(f"{k} = ?" for k in allowed)
            self._exec(f"UPDATE users SET {sets} WHERE id = ?", (*allowed.values(), uid))
        return self.get_user(uid)

    # calls -----------------------------------------------------------------------
    def insert_call(self, call_id: str, code: str, host_id: str) -> None:
        self._exec("INSERT INTO calls (id, invite_code, host_id, status, created_at) VALUES (?,?,?,?,?)",
                   (call_id, code, host_id, "waiting", time.time()))  # fmt: skip

    def add_participant(self, call_id: str, user_id: str, language: str) -> None:
        self._exec("INSERT OR REPLACE INTO call_participants (call_id, user_id, language, joined_at) VALUES (?,?,?,?)",
                   (call_id, user_id, language, time.time()))  # fmt: skip

    def mark_started(self, call_id: str) -> None:
        self._exec("UPDATE calls SET status = 'active', started_at = COALESCE(started_at, ?) WHERE id = ?",
                   (time.time(), call_id))  # fmt: skip

    def mark_ended(self, call_id: str, utterances: int) -> None:
        self._exec("UPDATE calls SET status = 'ended', ended_at = ?, utterances = ? WHERE id = ? AND status != 'ended'",
                   (time.time(), utterances, call_id))  # fmt: skip

    def history(self, user_id: str, limit: int = 30) -> list[dict]:
        rows = self._exec(
            """SELECT c.id, c.status, c.created_at, c.started_at, c.ended_at, c.utterances,
                      me.language AS my_language, other.user_id AS peer_id, other.language AS peer_language,
                      u.display_name AS peer_name, u.is_demo AS peer_is_demo
               FROM calls c
               JOIN call_participants me ON me.call_id = c.id AND me.user_id = ?
               LEFT JOIN call_participants other ON other.call_id = c.id AND other.user_id != ?
               LEFT JOIN users u ON u.id = other.user_id
               ORDER BY c.created_at DESC LIMIT ?""",
            (user_id, user_id, limit),
        )
        return [dict(r) for r in rows]

    # favourites (only people you have actually called) ---------------------------------
    def set_favourite(self, user_id: str, contact_id: str, on: bool) -> None:
        if on:
            self._exec("INSERT OR IGNORE INTO favourites (user_id, contact_id, created_at) VALUES (?,?,?)",
                       (user_id, contact_id, time.time()))  # fmt: skip
        else:
            self._exec("DELETE FROM favourites WHERE user_id = ? AND contact_id = ?", (user_id, contact_id))

    def have_called(self, user_id: str, contact_id: str) -> bool:
        return bool(self._exec(
            """SELECT 1 FROM call_participants a JOIN call_participants b ON a.call_id = b.call_id
               WHERE a.user_id = ? AND b.user_id = ? LIMIT 1""", (user_id, contact_id)))  # fmt: skip

    def favourites(self, user_id: str) -> list[dict]:
        rows = self._exec(
            """SELECT u.id, u.display_name, u.language, u.is_demo FROM favourites f
               JOIN users u ON u.id = f.contact_id WHERE f.user_id = ? ORDER BY f.created_at DESC""", (user_id,))  # fmt: skip
        return [dict(r) for r in rows]

    # voicemails (text only; the audio is never stored) -------------------------------------
    def insert_voicemail(self, sender_id: str, recipient_id: str, source_lang: str, target_lang: str,
                         duration_ms: int) -> str:  # fmt: skip
        vid = uuid.uuid4().hex
        self._exec("""INSERT INTO voicemails (id, sender_id, recipient_id, source_lang, target_lang, status,
                      duration_ms, created_at) VALUES (?,?,?,?,?,'processing',?,?)""",
                   (vid, sender_id, recipient_id, source_lang, target_lang, duration_ms, time.time()))  # fmt: skip
        return vid

    def finish_voicemail(self, vid: str, status: str, original: str | None = None, translation: str | None = None,
                         source_lang: str | None = None, error: str | None = None) -> None:  # fmt: skip
        self._exec("""UPDATE voicemails SET status = ?, original = ?, translation = ?, error = ?,
                      source_lang = COALESCE(?, source_lang) WHERE id = ?""",
                   (status, original, translation, error, source_lang, vid))  # fmt: skip

    def get_voicemail(self, vid: str) -> dict | None:
        rows = self._exec("SELECT * FROM voicemails WHERE id = ?", (vid,))
        return dict(rows[0]) if rows else None

    def mark_heard(self, vid: str) -> None:
        self._exec("UPDATE voicemails SET heard_at = COALESCE(heard_at, ?) WHERE id = ?", (time.time(), vid))

    def delete_voicemail(self, vid: str) -> None:
        self._exec("DELETE FROM voicemails WHERE id = ?", (vid,))

    def purge_voicemails(self, older_than: float) -> None:
        self._exec("DELETE FROM voicemails WHERE created_at < ?", (older_than,))

    def voicemails(self, user_id: str, sent: bool, limit: int = 50) -> list[dict]:
        mine, other = ("sender_id", "recipient_id") if sent else ("recipient_id", "sender_id")
        ready = "" if sent else "AND v.status = 'ready'"
        rows = self._exec(
            f"""SELECT v.*, u.display_name AS other_name, u.language AS other_language, u.is_demo AS other_is_demo
                FROM voicemails v LEFT JOIN users u ON u.id = v.{other}
                WHERE v.{mine} = ? {ready} ORDER BY v.created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        return [dict(r) for r in rows]

    def sent_today(self, user_id: str, since: float) -> int:
        rows = self._exec("SELECT COUNT(*) AS n FROM voicemails WHERE sender_id = ? AND created_at >= ?", (user_id, since))
        return int(rows[0]["n"])
