"""SQLite storage: users, sign-in sessions, call metadata, favourites, voicemail text and chat.

Live-call audio and live-call transcripts are never stored here. Conversation content that must wait for its
reader is kept for a fixed time only: voicemail text (7 days, or until deleted) and chat messages with their
voice clips (30 days by default, `CHAT_RETENTION_DAYS`). Refresh tokens are stored only as hashes.
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
    is_demo INTEGER NOT NULL DEFAULT 0, language TEXT NOT NULL DEFAULT 'ta-IN', username TEXT UNIQUE, created_at REAL NOT NULL,
    allow_calls TEXT NOT NULL DEFAULT 'contacts'
);
CREATE TABLE IF NOT EXISTS contacts (
    user_id TEXT NOT NULL, contact_id TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY (user_id, contact_id)
);
CREATE TABLE IF NOT EXISTS blocks (
    user_id TEXT NOT NULL, blocked_id TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY (user_id, blocked_id)
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

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, refresh_hash TEXT NOT NULL UNIQUE, prev_refresh_hash TEXT,
    device TEXT, created_at REAL NOT NULL, last_used_at REAL NOT NULL, expires_at REAL NOT NULL, revoked_at REAL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
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


# columns added after the first release: (table, column, definition), added to existing databases on start
_COLUMNS = [
    ("users", "read_receipts", "INTEGER NOT NULL DEFAULT 1"),
    ("users", "chat_retention_days", "INTEGER NOT NULL DEFAULT 30"),
    ("users", "phone_hash", "TEXT"),
    ("users", "username_norm", "TEXT"),
    ("users", "avatar", "TEXT"),
    ("messages", "expires_at", "REAL"),
    ("messages", "deleted_at", "REAL"),
    ("conversation_members", "last_delivered_at", "REAL NOT NULL DEFAULT 0"),
]
_SCHEMA += """
CREATE TABLE IF NOT EXISTS hidden_messages (
    user_id TEXT NOT NULL, message_id TEXT NOT NULL, PRIMARY KEY (user_id, message_id)
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
                if "allow_calls" not in cols:
                    self._db.execute("ALTER TABLE users ADD COLUMN allow_calls TEXT NOT NULL DEFAULT 'contacts'")
            self._db.executescript(_SCHEMA)
            for table, col, ddl in _COLUMNS:
                cols = [r[1] for r in self._db.execute(f"PRAGMA table_info({table})").fetchall()]
                if col not in cols:
                    self._db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            self._db.execute("UPDATE users SET username_norm = LOWER(TRIM(username)) WHERE username IS NOT NULL AND (username_norm IS NULL OR username_norm != LOWER(TRIM(username)))")
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username ON users(username)")
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_norm ON users(username_norm)")
            self._db.commit()

    def _exec(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, args)
            rows = cur.fetchall()
            self._db.commit()
            return rows

    # users -----------------------------------------------------------------------
    def create_user(self, display_name: str, email: str | None, password_hash: str | None, is_demo: bool, username: str | None = None, language: str = "ta-IN") -> dict:
        uid = uuid.uuid4().hex
        uname = username.strip() if username else None
        uname_norm = uname.lower() if uname else None
        self._exec("INSERT INTO users (id, email, display_name, password_hash, is_demo, username, username_norm, language, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (uid, email, display_name.strip(), password_hash, int(is_demo), uname, uname_norm, language, time.time()))  # fmt: skip
        return self.get_user(uid)  # type: ignore[return-value]

    def get_user(self, uid: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE id = ?", (uid,))
        return dict(rows[0]) if rows else None

    def get_user_by_email(self, email: str) -> dict | None:
        rows = self._exec("SELECT * FROM users WHERE email = ?", (email,))
        return dict(rows[0]) if rows else None

    def get_user_by_username(self, username: str) -> dict | None:
        u = username.strip().lstrip("@").lower()
        rows = self._exec("SELECT * FROM users WHERE username_norm = ?", (u,))
        return dict(rows[0]) if rows else None

    def is_username_available(self, username: str, exclude_user_id: str | None = None) -> bool:
        u = username.strip().lstrip("@").lower()
        if exclude_user_id:
            rows = self._exec("SELECT 1 FROM users WHERE username_norm = ? AND id != ? LIMIT 1", (u, exclude_user_id))
        else:
            rows = self._exec("SELECT 1 FROM users WHERE username_norm = ? LIMIT 1", (u,))
        return len(rows) == 0

    def search_users(self, query: str, current_user_id: str, limit: int = 25) -> list[dict]:
        cleaned = query.strip().lstrip("@").strip().lower()
        if not cleaned:
            return []
        prefix = f"{cleaned}%"
        substr = f"%{cleaned}%"
        rows = self._exec(
            """SELECT id, display_name, username, avatar FROM users
               WHERE (username_norm = ? OR username_norm LIKE ? OR LOWER(display_name) LIKE ?) AND id != ?
                 AND id NOT IN (SELECT blocked_id FROM blocks WHERE user_id = ?)
                 AND id NOT IN (SELECT user_id FROM blocks WHERE blocked_id = ?)
               ORDER BY (CASE WHEN username_norm = ? THEN 0 WHEN username_norm LIKE ? THEN 1 ELSE 2 END), display_name ASC LIMIT ?""",
            (cleaned, prefix, substr, current_user_id, current_user_id, current_user_id, cleaned, prefix, limit),
        )
        return [{"id": r["id"], "display_name": r["display_name"], "username": r["username"], "avatar": r["avatar"]} for r in rows]

    def match_phone_hashes(self, hashes: list[str]) -> list[dict]:
        if not hashes:
            return []
        unique_hashes = list(set(h.strip().lower() for h in hashes if h and h.strip()))
        out: list[dict] = []
        chunk_size = 200
        for i in range(0, len(unique_hashes), chunk_size):
            chunk = unique_hashes[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._exec(
                f"""SELECT id, display_name, username, language, is_demo, phone_hash FROM users
                   WHERE phone_hash IN ({placeholders}) AND phone_hash IS NOT NULL""",
                tuple(chunk),
            )
            out.extend([dict(r) for r in rows])
        return out

    def update_user(self, uid: str, **fields: Any) -> dict | None:
        if "username" in fields and fields["username"] is not None:
            fields["username"] = fields["username"].strip()
            fields["username_norm"] = fields["username"].lower()
        allowed = {k: v for k, v in fields.items()
                   if k in ("display_name", "language", "username", "username_norm", "avatar", "allow_calls", "read_receipts",
                            "chat_retention_days", "phone_hash") and v is not None}  # fmt: skip
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
        days = self._exec("""SELECT MIN(u.chat_retention_days) AS d FROM conversation_members m
                              JOIN users u ON u.id = m.user_id WHERE m.conversation_id = ?""", (conv_id,))  # fmt: skip
        keep_days = int(days[0]["d"]) if days and days[0]["d"] else 30
        self._exec(
            """INSERT INTO messages (id, conversation_id, sender_id, sender_name, source_lang,
                          original_text, audio_id, duration_ms, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, conv_id, sender_id, sender_name, source_lang, original_text.strip(), audio_id, duration_ms, now,
             now + keep_days * 86400),
        )
        self._exec("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        self._exec("UPDATE conversation_members SET last_read_at = ? WHERE conversation_id = ? AND user_id = ?",
                   (now, conv_id, sender_id))
        rows = self._exec("SELECT * FROM messages WHERE id = ?", (mid,))
        return dict(rows[0])

    def conversation_of_audio(self, audio_id: str) -> str | None:
        rows = self._exec("SELECT conversation_id FROM messages WHERE audio_id = ?", (audio_id,))
        return rows[0]["conversation_id"] if rows else None

    def purge_messages(self, older_than: float) -> list[str]:
        """Deletes chat messages past their expiry (older ones without an expiry: older than the cutoff), with their
        translations; returns their voice clip ids."""
        now = time.time()
        where = "(expires_at IS NOT NULL AND expires_at < ?) OR (expires_at IS NULL AND created_at < ?)"
        old = self._exec(f"SELECT id, audio_id FROM messages WHERE {where}", (now, older_than))
        if not old:
            return []
        ids = [r["id"] for r in old]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            self._exec(f"DELETE FROM message_translations WHERE message_id IN ({marks})", tuple(chunk))
            self._exec(f"DELETE FROM hidden_messages WHERE message_id IN ({marks})", tuple(chunk))
            self._exec(f"DELETE FROM messages WHERE id IN ({marks})", tuple(chunk))
        return [r["audio_id"] for r in old if r["audio_id"]]

    def get_message(self, mid: str) -> dict | None:
        rows = self._exec("SELECT * FROM messages WHERE id = ?", (mid,))
        return dict(rows[0]) if rows else None

    def delete_message_for_everyone(self, mid: str) -> str | None:
        """Removes a message's content for everyone (a "deleted" marker stays); returns its voice clip id."""
        msg = self.get_message(mid)
        if msg is None:
            return None
        self._exec("UPDATE messages SET original_text = '', audio_id = NULL, duration_ms = 0, deleted_at = ? WHERE id = ?",
                   (time.time(), mid))  # fmt: skip
        self._exec("DELETE FROM message_translations WHERE message_id = ?", (mid,))
        return msg["audio_id"]

    def hide_message(self, user_id: str, mid: str) -> None:
        self._exec("INSERT OR IGNORE INTO hidden_messages (user_id, message_id) VALUES (?, ?)", (user_id, mid))

    def hidden_message_ids(self, user_id: str, conv_id: str) -> set[str]:
        rows = self._exec("""SELECT h.message_id FROM hidden_messages h JOIN messages m ON m.id = h.message_id
                             WHERE h.user_id = ? AND m.conversation_id = ?""", (user_id, conv_id))  # fmt: skip
        return {r["message_id"] for r in rows}

    def mark_delivered(self, conv_id: str, user_id: str) -> None:
        self._exec("""UPDATE conversation_members SET last_delivered_at = ? WHERE conversation_id = ? AND user_id = ?""",
                   (time.time(), conv_id, user_id))  # fmt: skip

    def receipts(self, conv_id: str, except_user: str) -> list[dict]:
        """For each other member: when they last received and last read the chat, and whether they share reads."""
        rows = self._exec("""SELECT m.user_id, m.last_read_at, m.last_delivered_at, u.read_receipts
                             FROM conversation_members m JOIN users u ON u.id = m.user_id
                             WHERE m.conversation_id = ? AND m.user_id != ?""", (conv_id, except_user))  # fmt: skip
        return [dict(r) for r in rows]

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

    def mark_conversation_read(self, conv_id: str, user_id: str) -> bool:
        """Marks everything read; True when there were messages from others that had not been read yet."""
        rows = self._exec("""SELECT COUNT(*) AS n FROM messages msg JOIN conversation_members m
                             ON m.conversation_id = msg.conversation_id AND m.user_id = ?
                             WHERE msg.conversation_id = ? AND msg.sender_id != ? AND msg.created_at > m.last_read_at""",
                          (user_id, conv_id, user_id))  # fmt: skip
        now = time.time()
        self._exec("""UPDATE conversation_members SET last_read_at = ?, last_delivered_at = ?
                      WHERE conversation_id = ? AND user_id = ?""", (now, now, conv_id, user_id))  # fmt: skip
        return bool(rows and rows[0]["n"])

    def get_cached_translation(self, message_id: str, target_lang: str) -> str | None:
        rows = self._exec("SELECT translated_text FROM message_translations WHERE message_id = ? AND target_lang = ?",
                          (message_id, target_lang))
        return rows[0]["translated_text"] if rows else None

    def store_cached_translation(self, message_id: str, target_lang: str, translated_text: str) -> None:
        self._exec("INSERT OR REPLACE INTO message_translations (message_id, target_lang, translated_text, created_at) VALUES (?, ?, ?, ?)",
                   (message_id, target_lang, translated_text, time.time()))

    # sign-in sessions (refresh tokens stored as SHA-256 hashes only) ------------------------
    def create_session(self, user_id: str, refresh_hash: str, device: str | None, ttl_s: float) -> str:
        sid = uuid.uuid4().hex
        now = time.time()
        self._exec("""INSERT INTO sessions (id, user_id, refresh_hash, device, created_at, last_used_at, expires_at)
                      VALUES (?,?,?,?,?,?,?)""", (sid, user_id, refresh_hash, device, now, now, now + ttl_s))  # fmt: skip
        return sid

    def active_session(self, sid: str) -> dict | None:
        rows = self._exec("SELECT * FROM sessions WHERE id = ? AND revoked_at IS NULL AND expires_at > ?",
                          (sid, time.time()))  # fmt: skip
        return dict(rows[0]) if rows else None

    def session_by_refresh(self, refresh_hash: str) -> tuple[dict | None, bool]:
        """(session, reused): reused=True when the hash is an already-replaced token of that session."""
        rows = self._exec("SELECT * FROM sessions WHERE refresh_hash = ?", (refresh_hash,))
        if rows:
            return dict(rows[0]), False
        rows = self._exec("SELECT * FROM sessions WHERE prev_refresh_hash = ?", (refresh_hash,))
        return (dict(rows[0]), True) if rows else (None, False)

    def rotate_session(self, sid: str, new_hash: str, ttl_s: float) -> None:
        now = time.time()
        self._exec("""UPDATE sessions SET prev_refresh_hash = refresh_hash, refresh_hash = ?, last_used_at = ?,
                      expires_at = ? WHERE id = ?""", (new_hash, now, now + ttl_s, sid))  # fmt: skip

    def revoke_session(self, sid: str) -> None:
        self._exec("UPDATE sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE id = ?", (time.time(), sid))

    def revoke_other_sessions(self, user_id: str, keep_sid: str | None) -> int:
        rows = self._exec("SELECT id FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND id != ?",
                          (user_id, keep_sid or ""))  # fmt: skip
        for r in rows:
            self.revoke_session(r["id"])
        return len(rows)

    def sessions(self, user_id: str) -> list[dict]:
        rows = self._exec("""SELECT id, device, created_at, last_used_at FROM sessions
                             WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?
                             ORDER BY last_used_at DESC""", (user_id, time.time()))  # fmt: skip
        return [dict(r) for r in rows]

    def purge_sessions(self, older_than: float) -> None:
        self._exec("DELETE FROM sessions WHERE expires_at < ? OR revoked_at < ?", (older_than, older_than))

    # contacts and blocking ---------------------------------------------------------------
    def add_contact(self, user_id: str, contact_id: str) -> None:
        self._exec("INSERT OR IGNORE INTO contacts (user_id, contact_id, created_at) VALUES (?,?,?)",
                   (user_id, contact_id, time.time()))  # fmt: skip

    def remove_contact(self, user_id: str, contact_id: str) -> None:
        self._exec("DELETE FROM contacts WHERE user_id = ? AND contact_id = ?", (user_id, contact_id))

    def is_contact(self, user_id: str, contact_id: str) -> bool:
        return bool(self._exec("SELECT 1 FROM contacts WHERE user_id = ? AND contact_id = ?", (user_id, contact_id)))

    def contacts(self, user_id: str) -> list[dict]:
        rows = self._exec(
            """SELECT u.id, u.display_name, u.username, u.language, u.is_demo FROM contacts c
               JOIN users u ON u.id = c.contact_id WHERE c.user_id = ? ORDER BY LOWER(u.display_name)""", (user_id,))  # fmt: skip
        return [dict(r) for r in rows]

    def block(self, user_id: str, blocked_id: str) -> None:
        self._exec("INSERT OR IGNORE INTO blocks (user_id, blocked_id, created_at) VALUES (?,?,?)",
                   (user_id, blocked_id, time.time()))  # fmt: skip
        self.remove_contact(user_id, blocked_id)

    def unblock(self, user_id: str, blocked_id: str) -> None:
        self._exec("DELETE FROM blocks WHERE user_id = ? AND blocked_id = ?", (user_id, blocked_id))

    def blocked_users(self, user_id: str) -> list[dict]:
        rows = self._exec(
            """SELECT u.id, u.display_name, u.username, u.language, u.is_demo FROM blocks b
               JOIN users u ON u.id = b.blocked_id WHERE b.user_id = ? ORDER BY b.created_at DESC""", (user_id,))  # fmt: skip
        return [dict(r) for r in rows]

    def either_blocked(self, a: str, b: str) -> bool:
        return bool(self._exec("""SELECT 1 FROM blocks WHERE (user_id = ? AND blocked_id = ?)
                                  OR (user_id = ? AND blocked_id = ?)""", (a, b, b, a)))  # fmt: skip

    # account deletion ----------------------------------------------------------------------
    def delete_user(self, uid: str) -> list[str]:
        """Removes a user and everything stored about them. Returns voice clip ids whose files must be deleted.

        Their chat messages go entirely (other members see them disappear); chats left with no members go too.
        Call records keep only the other person's side.
        """
        clips = [r["audio_id"] for r in self._exec(
            "SELECT audio_id FROM messages WHERE sender_id = ? AND audio_id IS NOT NULL", (uid,))]  # fmt: skip
        mine = "SELECT id FROM messages WHERE sender_id = ?"
        self._exec(f"DELETE FROM message_translations WHERE message_id IN ({mine})", (uid,))
        self._exec(f"DELETE FROM hidden_messages WHERE user_id = ? OR message_id IN ({mine})", (uid, uid))
        self._exec("DELETE FROM messages WHERE sender_id = ?", (uid,))
        self._exec("DELETE FROM conversation_members WHERE user_id = ?", (uid,))
        empty = "SELECT id FROM conversations WHERE id NOT IN (SELECT conversation_id FROM conversation_members)"
        clips += [r["audio_id"] for r in self._exec(
            f"SELECT audio_id FROM messages WHERE conversation_id IN ({empty}) AND audio_id IS NOT NULL")]  # fmt: skip
        self._exec(f"DELETE FROM message_translations WHERE message_id IN "
                   f"(SELECT id FROM messages WHERE conversation_id IN ({empty}))")  # fmt: skip
        self._exec(f"DELETE FROM messages WHERE conversation_id IN ({empty})")
        self._exec(f"DELETE FROM conversations WHERE id IN ({empty})")
        self._exec("DELETE FROM voicemails WHERE sender_id = ? OR recipient_id = ?", (uid, uid))
        self._exec("DELETE FROM contacts WHERE user_id = ? OR contact_id = ?", (uid, uid))
        self._exec("DELETE FROM blocks WHERE user_id = ? OR blocked_id = ?", (uid, uid))
        self._exec("DELETE FROM favourites WHERE user_id = ? OR contact_id = ?", (uid, uid))
        self._exec("DELETE FROM call_participants WHERE user_id = ?", (uid,))
        self._exec("DELETE FROM calls WHERE id NOT IN (SELECT call_id FROM call_participants)")
        self._exec("DELETE FROM sessions WHERE user_id = ?", (uid,))
        self._exec("DELETE FROM users WHERE id = ?", (uid,))
        return clips
