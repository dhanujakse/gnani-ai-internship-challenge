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
    is_demo INTEGER NOT NULL DEFAULT 0, language TEXT NOT NULL DEFAULT 'ta-IN', username TEXT UNIQUE, created_at REAL NOT NULL
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

-- Multilingual Global Chat & Group Messaging
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, is_group INTEGER NOT NULL DEFAULT 0, name TEXT,
    created_by TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS convs_updated ON conversations(updated_at DESC);
CREATE TABLE IF NOT EXISTS conversation_members (
    conversation_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
    joined_at REAL NOT NULL, last_read_at REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (conversation_id, user_id)
);
CREATE INDEX IF NOT EXISTS conv_members_user ON conversation_members(user_id);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, sender_id TEXT NOT NULL, sender_name TEXT NOT NULL,
    source_lang TEXT NOT NULL, original_text TEXT NOT NULL, audio_id TEXT, duration_ms INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conv_time ON messages(conversation_id, created_at ASC);
CREATE TABLE IF NOT EXISTS message_translations (
    message_id TEXT NOT NULL, target_lang TEXT NOT NULL, translated_text TEXT NOT NULL,
    created_at REAL NOT NULL, PRIMARY KEY (message_id, target_lang)
);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            # Check if users table exists and needs migration before running remaining schema
            user_table = self._db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            if user_table:
                cols = [r[1] for r in self._db.execute("PRAGMA table_info(users)").fetchall()]
                if "username" not in cols:
                    self._db.execute("ALTER TABLE users ADD COLUMN username TEXT")
            self._db.executescript(_SCHEMA)
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username ON users(username)")
            self._db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, args)
            rows = cur.fetchall()
            self._db.commit()
            return rows

    # users -----------------------------------------------------------------------
    def create_user(self, display_name: str, email: str | None, password_hash: str | None, is_demo: bool, username: str | None = None) -> dict:
        uid = uuid.uuid4().hex
        self._exec("INSERT INTO users (id, email, display_name, password_hash, is_demo, username, created_at) VALUES (?,?,?,?,?,?,?)",
                   (uid, email, display_name, password_hash, int(is_demo), username, time.time()))  # fmt: skip
        return self.get_user(uid)  # type: ignore[return-value]

    def get_user(self, uid: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE id = ?", (uid,))
        return dict(rows[0]) if rows else None

    def get_user_by_email(self, email: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE email = ?", (email,))
        return dict(rows[0]) if rows else None

    def get_user_by_username(self, username: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
        return dict(rows[0]) if rows else None

    def is_username_available(self, username: str, exclude_user_id: str | None = None) -> bool:
        u = username.strip().lower()
        if exclude_user_id:
            rows = self._exec("SELECT 1 FROM users WHERE LOWER(username) = ? AND id != ? LIMIT 1", (u, exclude_user_id))
        else:
            rows = self._exec("SELECT 1 FROM users WHERE LOWER(username) = ? LIMIT 1", (u,))
        return len(rows) == 0

    def search_users(self, query: str, current_user_id: str, limit: int = 25) -> list[dict]:
        q = f"%{query.strip().lower()}%"
        rows = self._exec(
            """SELECT id, display_name, username, language, is_demo FROM users
               WHERE (LOWER(username) LIKE ? OR LOWER(display_name) LIKE ?) AND id != ?
               ORDER BY display_name ASC LIMIT ?""",
            (q, q, current_user_id, limit),
        )
        return [dict(r) for r in rows]

    def update_user(self, uid: str, **fields: Any) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in ("display_name", "language", "username") and v is not None}
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

    # Multilingual Chat & Group Messaging ---------------------------------
    def get_or_create_direct_conversation(self, user_id_1: str, user_id_2: str) -> dict:
        # Check if direct conversation already exists between these 2 users
        rows = self._exec(
            """SELECT c.id FROM conversations c
               JOIN conversation_members m1 ON m1.conversation_id = c.id AND m1.user_id = ?
               JOIN conversation_members m2 ON m2.conversation_id = c.id AND m2.user_id = ?
               WHERE c.is_group = 0 LIMIT 1""",
            (user_id_1, user_id_2),
        )
        if rows:
            return self.get_conversation(rows[0]["id"], user_id_1)  # type: ignore[return-value]

        cid = uuid.uuid4().hex
        now = time.time()
        self._exec("INSERT INTO conversations (id, is_group, name, created_by, created_at, updated_at) VALUES (?, 0, NULL, ?, ?, ?)",
                   (cid, user_id_1, now, now))
        self._exec("INSERT INTO conversation_members (conversation_id, user_id, role, joined_at, last_read_at) VALUES (?, ?, 'member', ?, ?)",
                   (cid, user_id_1, now, now))
        self._exec("INSERT INTO conversation_members (conversation_id, user_id, role, joined_at, last_read_at) VALUES (?, ?, 'member', ?, 0)",
                   (cid, user_id_2, now))
        return self.get_conversation(cid, user_id_1)  # type: ignore[return-value]

    def create_group_conversation(self, creator_id: str, name: str, member_ids: list[str]) -> dict:
        cid = uuid.uuid4().hex
        now = time.time()
        self._exec("INSERT INTO conversations (id, is_group, name, created_by, created_at, updated_at) VALUES (?, 1, ?, ?, ?, ?)",
                   (cid, name.strip(), creator_id, now, now))
        self._exec("INSERT INTO conversation_members (conversation_id, user_id, role, joined_at, last_read_at) VALUES (?, ?, 'admin', ?, ?)",
                   (cid, creator_id, now, now))
        unique_members = set(member_ids) - {creator_id}
        for uid in unique_members:
            self._exec("INSERT OR IGNORE INTO conversation_members (conversation_id, user_id, role, joined_at, last_read_at) VALUES (?, ?, 'member', ?, 0)",
                       (cid, uid, now))
        return self.get_conversation(cid, creator_id)  # type: ignore[return-value]

    def get_conversation(self, conv_id: str, for_user_id: str | None = None) -> dict | None:
        rows = self._exec("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        if not rows:
            return None
        conv = dict(rows[0])
        conv["is_group"] = bool(conv["is_group"])
        members = self.get_conversation_members(conv_id)
        conv["members"] = members
        conv["member_count"] = len(members)

        if not conv["is_group"] and for_user_id:
            peer = next((m for m in members if m["id"] != for_user_id), None)
            if peer:
                conv["peer"] = peer
                conv["name"] = peer["display_name"]
            else:
                conv["name"] = "Direct Chat"

        # Last message
        last_msg = self._exec("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1", (conv_id,))
        conv["last_message"] = dict(last_msg[0]) if last_msg else None

        # Unread count for for_user_id
        if for_user_id:
            member_row = self._exec("SELECT last_read_at FROM conversation_members WHERE conversation_id = ? AND user_id = ?",
                                    (conv_id, for_user_id))
            last_read = float(member_row[0]["last_read_at"]) if member_row else 0.0
            unread_rows = self._exec("SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = ? AND sender_id != ? AND created_at > ?",
                                     (conv_id, for_user_id, last_read))
            conv["unread_count"] = int(unread_rows[0]["cnt"]) if unread_rows else 0
        else:
            conv["unread_count"] = 0

        return conv

    def get_conversation_members(self, conv_id: str) -> list[dict]:
        rows = self._exec(
            """SELECT u.id, u.id AS user_id, u.display_name, u.username, u.language, u.is_demo, m.role, m.joined_at
               FROM conversation_members m
               JOIN users u ON u.id = m.user_id
               WHERE m.conversation_id = ? ORDER BY m.joined_at ASC""",
            (conv_id,),
        )
        return [dict(r) for r in rows]

    def is_conversation_member(self, conv_id: str, user_id: str) -> bool:
        rows = self._exec("SELECT 1 FROM conversation_members WHERE conversation_id = ? AND user_id = ? LIMIT 1",
                          (conv_id, user_id))
        return len(rows) > 0

    def get_member_role(self, conv_id: str, user_id: str) -> str | None:
        rows = self._exec("SELECT role FROM conversation_members WHERE conversation_id = ? AND user_id = ? LIMIT 1",
                          (conv_id, user_id))
        return rows[0]["role"] if rows else None

    def add_conversation_member(self, conv_id: str, user_id: str, role: str = "member") -> bool:
        now = time.time()
        self._exec("INSERT OR IGNORE INTO conversation_members (conversation_id, user_id, role, joined_at, last_read_at) VALUES (?, ?, ?, ?, ?)",
                   (conv_id, user_id, role, now, 0))
        self._exec("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        return True

    def remove_conversation_member(self, conv_id: str, user_id: str) -> bool:
        self._exec("DELETE FROM conversation_members WHERE conversation_id = ? AND user_id = ?", (conv_id, user_id))
        self._exec("UPDATE conversations SET updated_at = ? WHERE id = ?", (time.time(), conv_id))
        # If no members left, remove conversation
        cnt = self._exec("SELECT COUNT(*) AS cnt FROM conversation_members WHERE conversation_id = ?", (conv_id,))
        if cnt and cnt[0]["cnt"] == 0:
            self._exec("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            self._exec("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return True

    def list_user_conversations(self, user_id: str, is_group: bool | None = None) -> list[dict]:
        filter_sql = ""
        args: list[Any] = [user_id]
        if is_group is not None:
            filter_sql = "AND c.is_group = ?"
            args.append(int(is_group))
        rows = self._exec(
            f"""SELECT c.id FROM conversations c
                JOIN conversation_members m ON m.conversation_id = c.id AND m.user_id = ?
                WHERE 1=1 {filter_sql}
                ORDER BY c.updated_at DESC""",
            tuple(args),
        )
        result = []
        for r in rows:
            c = self.get_conversation(r["id"], user_id)
            if c:
                result.append(c)
        return result

    def insert_message(self, conv_id: str, sender_id: str, sender_name: str, source_lang: str,
                       original_text: str, audio_id: str | None = None, duration_ms: int = 0) -> dict:
        mid = uuid.uuid4().hex
        now = time.time()
        self._exec(
            """INSERT INTO messages (id, conversation_id, sender_id, sender_name, source_lang,
                          original_text, audio_id, duration_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, conv_id, sender_id, sender_name, source_lang, original_text.strip(), audio_id, duration_ms, now),
        )
        self._exec("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        self._exec("UPDATE conversation_members SET last_read_at = ? WHERE conversation_id = ? AND user_id = ?",
                   (now, conv_id, sender_id))
        rows = self._exec("SELECT * FROM messages WHERE id = ?", (mid,))
        return dict(rows[0])

    def get_messages(self, conv_id: str, limit: int = 60, before: float | None = None) -> list[dict]:
        if before:
            rows = self._exec(
                """SELECT * FROM messages WHERE conversation_id = ? AND created_at < ?
                   ORDER BY created_at DESC LIMIT ?""",
                (conv_id, before, limit),
            )
        else:
            rows = self._exec(
                """SELECT * FROM messages WHERE conversation_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (conv_id, limit),
            )
        msgs = [dict(r) for r in rows]
        msgs.reverse()  # oldest first
        return msgs

    def mark_conversation_read(self, conv_id: str, user_id: str) -> None:
        self._exec("UPDATE conversation_members SET last_read_at = ? WHERE conversation_id = ? AND user_id = ?",
                   (time.time(), conv_id, user_id))

    def get_cached_translation(self, message_id: str, target_lang: str) -> str | None:
        rows = self._exec("SELECT translated_text FROM message_translations WHERE message_id = ? AND target_lang = ?",
                          (message_id, target_lang))
        return rows[0]["translated_text"] if rows else None

    def store_cached_translation(self, message_id: str, target_lang: str, translated_text: str) -> None:
        self._exec("INSERT OR REPLACE INTO message_translations (message_id, target_lang, translated_text, created_at) VALUES (?, ?, ?, ?)",
                   (message_id, target_lang, translated_text, time.time()))
