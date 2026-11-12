"""Sarvagyan API.

    cd server && uv run uvicorn sarvagyan_server.main:app --host 0.0.0.0 --port 8787

REST (JSON, Bearer token):
  POST /v1/auth/register | /v1/auth/login | /v1/auth/demo      GET/PATCH /v1/me
  GET  /v1/languages   GET /v1/ice-servers   GET /v1/diagnostics
  POST /v1/calls  -> {call_id, invite_code, invite_link}       POST /v1/calls/join {code}
  GET  /v1/calls/history   GET/PUT/DELETE /v1/contacts/favourites[/{id}]
  POST /v1/voicemails?to=<user id or email>&language=&auto_detect=  (body: raw PCM s16le mono 16 kHz, <= 60 s)
  GET  /v1/voicemails -> {inbox, sent, unread}   GET /v1/voicemails/{id}/audio (translated voice, PCM)
  POST /v1/voicemails/{id}/heard   DELETE /v1/voicemails/{id}
WebSocket:  /v1/calls/{call_id}/ws   (Authorization: Bearer <token>)
  client -> server: {"type":"hello", language, auto_detect, voice, speed, translate_audio}
                    {"type":"signal", payload}  {"type":"settings", ...}  {"type":"retry", id}  {"type":"leave"}
                    binary = mic PCM s16le mono 16 kHz (for translation only)
  server -> client: joined, peer_joined{initiator}, peer_reconnecting, peer_left, signal, pipeline,
                    speech_activity, utterance{id, stage, ...}, tts_start, binary PCM, tts_end, error, notice
"""

import asyncio
import contextlib
import gzip
import hmac
import inspect
import json
import logging
import re
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any

import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sarvagyan_server import __version__
from sarvagyan_server.config import Settings, get_settings
from sarvagyan_server.db import Database
from sarvagyan_server.languages import catalog, get_language
from sarvagyan_server.providers.gnani_stt import GnaniRecognizer
from sarvagyan_server.providers.base import ProviderError
from sarvagyan_server.providers.gnani_tts import GnaniSynthesizer
from sarvagyan_server.providers.mymemory import MyMemoryTranslator
from sarvagyan_server.credits import Meter, TtsCache
from sarvagyan_server.realtime import CallRoom, Participant
from sarvagyan_server import voicemail as vm
from sarvagyan_server.ratelimit import RateLimiter
from sarvagyan_server.security import (REFRESH_TTL_S, hash_password, hash_refresh_token, issue_token,
                                       new_invite_code, new_refresh_token, normalise_invite_code, token_claims,
                                       verify_password)

log = logging.getLogger("sarvagyan")
WAITING_TTL_S = 15 * 60
MAX_WS_TEXT = 64 * 1024
MAX_FRAME = 4096


class Services:
    """Everything stateful, created once per app (tests inject fakes)."""

    def __init__(self, settings: Settings, db: Database | None = None, recognizer=None, translator=None,
                 synthesizer_factory=None, voicemail_pace_s: float = vm.FRAME_S, push_sender=None) -> None:  # fmt: skip
        self.settings = settings
        self.db = db or Database(settings.data_path / "sarvagyan.sqlite3")
        key = settings.gnani_api_key.get_secret_value()
        self.recognizer = recognizer or GnaniRecognizer(key, settings.gnani_stt_url, settings.stt_model)
        self.translator = translator or MyMemoryTranslator(settings.mymemory_email)
        self.synthesizer_factory = synthesizer_factory or (
            lambda: GnaniSynthesizer(key, settings.gnani_tts_url, settings.tts_model))
        self.voicemail_pace_s = voicemail_pace_s
        self.voicemail = vm.VoicemailService(self.db, self.recognizer, self.translator, self.synthesizer_factory,
                                             pace_s=voicemail_pace_s)  # fmt: skip
        self.limits = RateLimiter()
        self._ring_tasks: set[asyncio.Task] = set()
        self._bg_tasks: set[asyncio.Task] = set()
        self.rooms: dict[str, CallRoom] = {}
        self.calls: dict[str, dict] = {}  # call_id -> {code, host, participants{uid: language}, created}
        self.by_code: dict[str, str] = {}
        self._usage: dict[tuple[str, str], int] = defaultdict(int)
        self.meter = Meter(settings)  # what the paid speech APIs were used for today (credits.py)
        self.tts_cache = TtsCache(max(0, settings.tts_cache_mb) * 1024 * 1024)
        self.chat_audio_dir = self.settings.data_path / "chat_audio"
        self.chat_audio_dir.mkdir(parents=True, exist_ok=True)
        self.avatar_dir = self.settings.data_path / "avatars"
        self.avatar_dir.mkdir(parents=True, exist_ok=True)
        self.chat_sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self.active_chats: dict[WebSocket, str] = {}
        self._call_acks: dict[str, dict] = {}
        self.push_sender = push_sender or self._default_push_sender

    def delete_custom_avatar(self, avatar: str | None) -> None:
        if avatar and avatar.startswith("custom:"):
            fid = avatar.removeprefix("custom:")
            if re.fullmatch(r"[0-9a-f]{32}", fid):
                for suffix in ("", "-thumb"):
                    with contextlib.suppress(OSError):
                        (self.avatar_dir / f"{fid}{suffix}.webp").unlink(missing_ok=True)

    async def _default_push_sender(self, tokens: list[str], title: str, body: str, data: dict[str, str]) -> None:
        sa_raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if not sa_raw or not tokens:
            return
        try:
            import google.auth.transport.requests
            from google.oauth2 import service_account
            sa_info = json.loads(sa_raw) if sa_raw.startswith("{") else json.loads(Path(sa_raw).read_text())
            creds = service_account.Credentials.from_service_account_info(
                sa_info, scopes=["https://www.googleapis.com/auth/firebase.messaging"]
            )
            creds.refresh(google.auth.transport.requests.Request())
            project_id = sa_info["project_id"]
            url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
            headers = {"Authorization": f"Bearer {creds.token}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                await asyncio.gather(*(
                    client.post(url, headers=headers, json={
                        "message": {
                            "token": tok,
                            "notification": {"title": title, "body": body},
                            "data": data,
                            "android": {"priority": "HIGH", "notification": {"channel_id": "chat_messages"}},
                        }
                    }) for tok in tokens
                ), return_exceptions=True)
        except Exception as exc:
            log.warning("fcm push error: %s", exc)

    def _spawn_bg(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self._bg_tasks.add(t)
        t.add_done_callback(self._bg_tasks.discard)
        return t

    async def _translate_for_targets(self, msg: dict, target_langs: set[str]) -> dict[str, tuple[str, bool]]:
        orig_text = msg.get("original_text") or ""
        source_lang = msg.get("source_lang") or "en-IN"
        source_base = source_lang.split("-")[0].lower()
        results: dict[str, tuple[str, bool]] = {}
        to_fetch: list[str] = []
        for lang in target_langs:
            if not orig_text or lang.split("-")[0].lower() == source_base or orig_text == "[Voice Message]":
                results[lang] = (orig_text, False)
            else:
                cached = self.db.get_cached_translation(msg["id"], lang)
                if cached:
                    results[lang] = (cached, cached != orig_text)
                else:
                    to_fetch.append(lang)
        if to_fetch:
            async def fetch_one(lang: str) -> tuple[str, str]:
                try:
                    tr = await self.translator.translate(orig_text, source_lang, lang)
                    self.db.store_cached_translation(msg["id"], lang, tr)
                    return lang, tr
                except Exception as exc:
                    log.warning("broadcast translation failed: %s", exc)
                    return lang, orig_text
            for lang, tr in await asyncio.gather(*(fetch_one(l) for l in to_fetch)):
                results[lang] = (tr, tr != orig_text)
        return results

    async def broadcast_chat_message(self, cid: str, msg: dict, event_type: str = "message") -> None:
        members = self.db.get_conversation_members(cid)
        connected_langs = {
            (m.get("language") or "en-IN")
            for m in members
            if self.chat_sockets.get(m.get("id") or m.get("user_id"))
        }
        all_langs = {(m.get("language") or "en-IN") for m in members}
        translations = await self._translate_for_targets(msg, connected_langs if event_type != "message" else all_langs)

        source_lang = msg.get("source_lang") or "en-IN"
        orig_text = msg.get("original_text") or ""
        audio_id = msg.get("audio_id")
        delivered_to: list[str] = []

        for m in members:
            uid = m.get("id") or m.get("user_id")
            socks = self.chat_sockets.get(uid)
            if not socks:
                continue
            target_lang = m.get("language") or "en-IN"
            translated_text, is_translated = translations.get(target_lang, (orig_text, False))
            payload = {
                "type": event_type,
                "conversation_id": cid,
                "message": {
                    "id": msg["id"],
                    "conversation_id": cid,
                    "sender_id": msg["sender_id"],
                    "sender_name": msg["sender_name"],
                    "sender_avatar": msg.get("sender_avatar"),
                    "source_lang": source_lang,
                    "original_text": orig_text,
                    "translated_text": translated_text,
                    "is_translated": is_translated,
                    "audio_id": audio_id,
                    "audio_url": f"/v1/chat/audio/{audio_id}" if audio_id else None,
                    "duration_ms": msg.get("duration_ms") or 0,
                    "tag": msg.get("tag"),
                    "created_at": msg["created_at"],
                },
            }
            raw = json.dumps(payload, ensure_ascii=False)
            dead = set()
            for ws in list(socks):
                try:
                    await ws.send_text(raw)
                except Exception:
                    dead.add(ws)
            socks.difference_update(dead)
            if socks and uid != msg["sender_id"]:
                self.db.mark_delivered(cid, uid)
                delivered_to.append(uid)

        for uid in delivered_to:
            await self.notify_user(msg["sender_id"], {"type": "chat_delivered", "conversation_id": cid, "user_id": uid})

        if event_type == "message":
            await self._send_push_for_message(cid, msg, members, translations)

    async def _send_push_for_message(self, cid: str, msg: dict, members: list[dict],
                                       translations: dict[str, tuple[str, bool]]) -> None:
        recipient_ids = [
            (m.get("id") or m.get("user_id")) for m in members
            if (m.get("id") or m.get("user_id")) != msg["sender_id"]
        ]
        # Skip users who currently have this exact chat open on an active socket
        open_users = {
            uid for uid in recipient_ids
            if any(self.active_chats.get(ws) == cid for ws in self.chat_sockets.get(uid, ()))
        }
        notify_ids = [uid for uid in recipient_ids if uid not in open_users]
        if not notify_ids:
            return
        tokens_by_user = self.db.get_device_tokens(notify_ids)
        if not tokens_by_user:
            return
        conv = self.db.get_conversation(cid, msg["sender_id"])
        is_group = bool(conv and conv.get("is_group"))
        title = f"{msg['sender_name']} · {conv['name']}" if is_group and conv and conv.get("name") else msg["sender_name"]
        tag = msg.get("tag")
        audio_id = msg.get("audio_id")
        lang_by_uid = {(m.get("id") or m.get("user_id")): (m.get("language") or "en-IN") for m in members}
        data = {"type": "chat_message", "conversation_id": cid, "message_id": msg["id"]}

        async def send_one(uid: str, toks: list[str]) -> None:
            if tag == "voicemail":
                body = "Voicemail"
            elif audio_id:
                body = "Voice message"
            else:
                preview = translations.get(lang_by_uid.get(uid, "en-IN"), (msg.get("original_text") or "", False))[0]
                body = preview if len(preview) <= 120 else preview[:117] + "…"
            await self.push_sender(toks, title, body, data)

        await asyncio.gather(*(send_one(uid, toks) for uid, toks in tokens_by_user.items() if toks), return_exceptions=True)

    async def process_voice_transcript(self, cid: str, mid: str, pcm: bytes, language: str) -> None:
        transcribed_text = ""
        detected_lang = language
        try:
            settle = 0.05 if self.voicemail_pace_s == 0 else vm.SETTLE_S
            transcribed_text, detected = await vm.transcribe(self.recognizer, pcm, language, pace_s=self.voicemail_pace_s, settle_s=settle)
            if detected:
                detected_lang = detected
        except Exception as exc:
            log.warning("background chat voice transcription error: %s", exc)
        if not transcribed_text:
            return
        updated = self.db.update_message_transcript(mid, transcribed_text, detected_lang)
        if updated:
            await self.broadcast_chat_message(cid, updated, event_type="message_updated")

    async def notify_members(self, cid: str, event: dict, except_user: str | None = None) -> None:
        for m in self.db.get_conversation_members(cid):
            if m["id"] != except_user:
                await self.notify_user(m["id"], event)

    async def broadcast_chat_typing(self, cid: str, sender_id: str, sender_name: str) -> None:
        members = self.db.get_conversation_members(cid)
        for m in members:
            uid = m.get("id") or m.get("user_id")
            if uid == sender_id:
                continue
            socks = self.chat_sockets.get(uid)
            if not socks:
                continue
            payload = {
                "type": "typing",
                "conversation_id": cid,
                "user_id": sender_id,
                "user_name": sender_name,
            }
            raw = json.dumps(payload, ensure_ascii=False)
            dead = set()
            for ws in list(socks):
                try:
                    await ws.send_text(raw)
                except Exception:
                    dead.add(ws)
            socks.difference_update(dead)

    def purge(self) -> None:
        """Deletes everything past its time limit: voicemail text, chat messages and voice clips, old sessions."""
        now = time.time()
        self.db.purge_voicemails(now - vm.RETENTION_S)
        for audio_id in self.db.purge_messages(now - self.settings.chat_retention_days * 86400):
            with contextlib.suppress(OSError):
                (self.chat_audio_dir / f"{audio_id}.pcm").unlink(missing_ok=True)
        self.db.purge_sessions(now - 86400)

    async def notify_user(self, user_id: str, event: dict, skip_session: str | None = None) -> bool:
        """Sends an event to every open app socket of a user. True if at least one phone received it."""
        sent = False
        for ws in list(self.chat_sockets.get(user_id, ())):
            if skip_session and getattr(ws, "session_id", None) == skip_session:
                continue
            try:
                await ws.send_text(json.dumps(event, ensure_ascii=False))
                sent = True
            except Exception:
                self.chat_sockets[user_id].discard(ws)
        return sent

    async def emit_call_state(self, user_id: str, call_id: str, state: str, **extra) -> tuple[bool, str]:
        ack_id = uuid.uuid4().hex[:12]
        self._call_acks[ack_id] = {"user_id": user_id, "call_id": call_id, "state": state, "acked": False, "ts": time.time()}
        if len(self._call_acks) > 2000:
            oldest = sorted(self._call_acks, key=lambda k: self._call_acks[k]["ts"])[:500]
            for k in oldest:
                self._call_acks.pop(k, None)
        sent = await self.notify_user(user_id, {"type": "call_state", "call_id": call_id, "state": state, "ack_id": ack_id, **extra})
        return sent, ack_id

    def ack_call_state(self, user_id: str, call_id: str, state: str, ack_id: str | None = None) -> None:
        if ack_id and ack_id in self._call_acks and self._call_acks[ack_id]["user_id"] == user_id:
            self._call_acks[ack_id]["acked"] = True
        log.info("call_state_ack user=%s call=%s state=%s ack_id=%s", user_id[:8], call_id[:8], state, ack_id)

    def start_ring_timer(self, cid: str) -> None:
        async def expire() -> None:
            await asyncio.sleep(self.settings.ring_timeout_s)
            call = self.calls.get(cid)
            if call and "ring" in call:
                await self.finish_ring(cid, call, "missed")

        task = asyncio.create_task(expire())
        self._ring_tasks.add(task)
        task.add_done_callback(self._ring_tasks.discard)

    async def finish_ring(self, cid: str, call: dict, outcome: str) -> None:
        """Ends a call nobody answered: declined, busy, cancelled by caller, or missed/no_answer (timeout)."""
        ring = call.pop("ring", None)
        if ring is None:
            return
        db_outcome = "no_answer" if outcome in ("missed", "no_answer") else outcome
        log.info("call state transition call=%s state=ended outcome=%s", cid[:8], db_outcome)
        callee = ring["to"]
        await self.notify_user(callee, {"type": "call_cancelled", "call_id": cid, "reason": outcome,
                                        "from_id": call["host"]})  # fmt: skip
        if outcome != "cancelled":
            u = self.db.get_user(callee)
            peer_name = u["display_name"] if u else None
            await self.notify_user(call["host"], {"type": f"call_{outcome}", "call_id": cid, "peer_id": callee,
                                                  "peer_name": peer_name})  # fmt: skip
            await self.emit_call_state(call["host"], cid, db_outcome, peer_id=callee, peer_name=peer_name)
        else:
            host = self.db.get_user(call["host"])
            await self.emit_call_state(callee, cid, "cancelled", peer_id=call["host"],
                                       peer_name=host["display_name"] if host else None)  # fmt: skip
        if outcome in ("missed", "no_answer"):
            host = self.db.get_user(call["host"])
            await self.emit_call_state(callee, cid, "no_answer", peer_id=call["host"],
                                       peer_name=host["display_name"] if host else None)  # fmt: skip
        self.db.mark_ended(cid, 0, outcome=db_outcome)
        self.calls.pop(cid, None)
        self.by_code.pop(call["code"], None)
        room = self.rooms.pop(cid, None)
        if room is not None:
            await room.close()

    def user_for_token(self, token: str) -> dict | None:
        """The signed-in user for an access token, with `session_id`; None if invalid, expired or revoked."""
        claims = token_claims(token, self.settings.signing_key) if token else None
        if not claims or not claims.get("sid"):
            return None
        sess = self.db.active_session(claims["sid"])
        if sess is None or sess["user_id"] != claims["uid"]:
            return None
        user = self.db.get_user(claims["uid"])
        return {**user, "session_id": sess["id"]} if user else None

    def quota(self, user_id: str) -> bool:
        key = (user_id, date.today().isoformat())
        self._usage[key] += 1
        return self._usage[key] <= self.settings.daily_utterance_cap

    def room(self, call_id: str) -> CallRoom:
        if call_id not in self.rooms:
            self.rooms[call_id] = CallRoom(call_id, self.recognizer, self.translator, self.synthesizer_factory,
                                           on_started=self.db.mark_started, quota=self.quota,
                                           on_empty=lambda: self.end_room(call_id), meter=self.meter,
                                           tts_cache=self.tts_cache, gate=self.settings.stt_silence_gate,
                                           idle_close_s=self.settings.stt_idle_close_s)  # fmt: skip
        return self.rooms[call_id]

    async def end_room(self, call_id: str) -> None:
        call = self.calls.get(call_id)
        if call and "ring" in call:
            await self.finish_ring(call_id, call, "cancelled")
            return
        room = self.rooms.pop(call_id, None)
        if room is not None:
            await room.close()
            self.db.mark_ended(call_id, room.utterance_count)
        call = self.calls.pop(call_id, None)
        if call:
            self.by_code.pop(call["code"], None)

    def expire_waiting(self) -> None:
        now = time.time()
        for cid, call in list(self.calls.items()):
            if cid not in self.rooms and now - call["created"] > WAITING_TTL_S:
                self.calls.pop(cid, None)
                self.by_code.pop(call["code"], None)
                self.db.mark_ended(cid, 0)


def create_app(services: Services | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = services or Services(get_settings())
        logging.basicConfig(level=app.state.services.settings.log_level,
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")  # fmt: skip
        async def cleaner() -> None:
            while True:
                with contextlib.suppress(Exception):
                    app.state.services.purge()
                await asyncio.sleep(3600)

        clean_task = asyncio.create_task(cleaner())
        yield
        clean_task.cancel()
        for cid in list(app.state.services.rooms):
            await app.state.services.end_room(cid)
        await app.state.services.voicemail.close()

    app = FastAPI(title="Sarvagyan API", version=__version__, lifespan=lifespan)
    if services is not None:
        app.state.services = services
    app.add_middleware(CORSMiddleware, allow_origins=[], allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"])

    def svc() -> Services:
        return app.state.services

    def client_ip(request: Request, s: Services) -> str:
        if s.settings.trust_proxy_headers and request.headers.get("cf-connecting-ip"):
            return request.headers["cf-connecting-ip"]
        return request.client.host if request.client else "unknown"

    def rate_limit(name: str, limit: int, window_s: float):
        def check(request: Request, s: Services = Depends(svc)) -> None:
            if not s.limits.allow(f"{name}:{client_ip(request, s)}", limit, window_s):
                raise HTTPException(429, "Too many requests. Please wait a moment and try again.")
        return check

    def current_user(authorization: str = Header(default=""), s: Services = Depends(svc)) -> dict:
        user = s.user_for_token(authorization.removeprefix("Bearer ").strip())
        if user is None:
            raise HTTPException(401, "Please sign in again.")
        return user

    def public_user(u: dict) -> dict:
        return {"id": u["id"], "display_name": u["display_name"], "username": u.get("username"), "email": u["email"],
                "avatar": u.get("avatar"), "is_demo": bool(u["is_demo"]), "language": u["language"],
                "allow_calls": u.get("allow_calls") or "contacts", "read_receipts": bool(u.get("read_receipts", 1)),
                "chat_retention_days": int(u.get("chat_retention_days") or 30)}  # fmt: skip

    def session(u: dict, s: Services, device: str | None) -> dict:
        refresh = new_refresh_token()
        sid = s.db.create_session(u["id"], hash_refresh_token(refresh), (device or "").strip()[:60] or None, REFRESH_TTL_S)
        return {"token": issue_token(u["id"], s.settings.signing_key, sid=sid), "refresh_token": refresh,
                "expires_in": 15 * 60, "user": public_user(u)}  # fmt: skip

    USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,24}$")

    def check_username_valid(u: str | None, db: Database, exclude_id: str | None = None) -> str | None:
        if not u:
            return None
        cleaned = u.strip().lstrip("@")
        if not USERNAME_RE.match(cleaned):
            raise HTTPException(422, "Username must be 3-24 characters containing only letters, numbers, and underscores.")
        if not db.is_username_available(cleaned, exclude_user_id=exclude_id):
            raise HTTPException(409, "Username is already taken.")
        return cleaned

    # --- auth -------------------------------------------------------------------------
    class RegisterIn(BaseModel):
        email: str = Field(min_length=3, max_length=200)
        password: str = Field(min_length=8, max_length=200)
        display_name: str = Field(min_length=1, max_length=60)
        username: str | None = None
        language: str | None = None
        device: str | None = Field(default=None, max_length=60)
        phone_hash: str | None = None

    class LoginIn(BaseModel):
        email: str = Field(max_length=200)
        password: str = Field(max_length=200)
        device: str | None = Field(default=None, max_length=60)

    class DemoIn(BaseModel):
        display_name: str = Field(min_length=1, max_length=60)
        username: str | None = None
        language: str | None = None
        device: str | None = Field(default=None, max_length=60)

    class RefreshIn(BaseModel):
        refresh_token: str = Field(min_length=10, max_length=200)

    @app.post("/v1/auth/register", dependencies=[Depends(rate_limit("register", 20, 3600))])
    def register(body: RegisterIn, s: Services = Depends(svc)) -> dict:
        email = body.email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(422, "Enter a valid email address.")
        if s.db.get_user_by_email(email):
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        uname = check_username_valid(body.username, s.db) if body.username else None
        lang = "en-IN"
        if body.language:
            try:
                get_language(body.language)
                lang = body.language
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        user = s.db.create_user(body.display_name.strip(), email, hash_password(body.password), is_demo=False, username=uname, language=lang)
        if body.phone_hash:
            s.db.update_user(user["id"], phone_hash=body.phone_hash.strip().lower())
        return session(user, s, body.device)

    @app.post("/v1/auth/login", dependencies=[Depends(rate_limit("login-ip", 60, 60))])
    def login(body: LoginIn, s: Services = Depends(svc)) -> dict:
        email = body.email.strip().lower()
        # per account: at most 5 tries a minute, and 10 failures lock sign-in for 15 minutes
        if s.limits.count(f"login-fail:{email}", 900) >= 10:
            raise HTTPException(429, "Too many failed sign-ins for this account. Try again in 15 minutes.")
        if not s.limits.allow(f"login:{email}", 5, 60):
            raise HTTPException(429, "Too many sign-in attempts. Please wait a minute.")
        user = s.db.get_user_by_email(email)
        if user is None or not user["password_hash"] or not verify_password(body.password, user["password_hash"]):
            s.limits.allow(f"login-fail:{email}", 1_000, 900)
            raise HTTPException(401, "Email or password is incorrect.")
        s.limits.reset(f"login-fail:{email}")
        return session(user, s, body.device)

    @app.post("/v1/auth/refresh", dependencies=[Depends(rate_limit("refresh", 60, 60))])
    def refresh(body: RefreshIn, s: Services = Depends(svc)) -> dict:
        sess, reused = s.db.session_by_refresh(hash_refresh_token(body.refresh_token))
        if sess is not None and reused:
            # an already-used refresh token came back: someone copied it. End that session everywhere.
            s.db.revoke_session(sess["id"])
            log.warning("refresh token reuse; session revoked sid=%s", sess["id"][:8])
            raise HTTPException(401, "Please sign in again.")
        if sess is None or sess["revoked_at"] is not None or sess["expires_at"] < time.time():
            raise HTTPException(401, "Please sign in again.")
        user = s.db.get_user(sess["user_id"])
        if user is None:
            raise HTTPException(401, "Please sign in again.")
        new = new_refresh_token()
        s.db.rotate_session(sess["id"], hash_refresh_token(new), REFRESH_TTL_S)
        return {"token": issue_token(user["id"], s.settings.signing_key, sid=sess["id"]), "refresh_token": new,
                "expires_in": 15 * 60, "user": public_user(user)}  # fmt: skip

    @app.post("/v1/auth/logout")
    def logout(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        s.db.revoke_session(user["session_id"])
        s.db.delete_device_token(user["id"])
        return {"ok": True}

    class PushTokenIn(BaseModel):
        token: str = Field(min_length=10, max_length=512)
        platform: str = Field(default="android", pattern="^(android|ios)$")

    @app.put("/v1/me/push-token")
    def register_push_token(body: PushTokenIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        s.db.upsert_device_token(user["id"], body.token.strip(), body.platform)
        return {"ok": True}

    @app.delete("/v1/me/push-token")
    def unregister_push_token(token: str | None = Query(default=None), user: dict = Depends(current_user),
                              s: Services = Depends(svc)) -> dict:  # fmt: skip
        s.db.delete_device_token(user["id"], token.strip() if token else None)
        return {"ok": True}

    class DeleteAccountIn(BaseModel):
        confirm: str = Field(max_length=20)
        password: str | None = Field(default=None, max_length=200)

    @app.delete("/v1/me", dependencies=[Depends(rate_limit("delete-account", 10, 3600))])
    async def delete_account(body: DeleteAccountIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        """Deletes the account and everything the server holds about it, at once. Cannot be undone."""
        if body.confirm != "DELETE":
            raise HTTPException(422, "Type DELETE to confirm.")
        if user["password_hash"] and not verify_password(body.password or "", user["password_hash"]):
            raise HTTPException(403, "Password is incorrect.")
        for cid, call in list(s.calls.items()):  # end any call they are in or being rung for
            if user["id"] in call["participants"] or (call.get("ring") or {}).get("to") == user["id"]:
                await s.end_room(cid)
                s.calls.pop(cid, None)
                s.by_code.pop(call["code"], None)
        for audio_id in s.db.delete_user(user["id"]):
            with contextlib.suppress(OSError):
                (s.chat_audio_dir / f"{audio_id}.pcm").unlink(missing_ok=True)
        s.delete_custom_avatar(user.get("avatar"))
        for ws in list(s.chat_sockets.pop(user["id"], ())):
            with contextlib.suppress(Exception):
                await ws.close(code=4401)
        log.info("account deleted uid=%s", user["id"][:8])
        return {"ok": True}

    @app.get("/v1/me/sessions")
    def my_sessions(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"sessions": [{"id": x["id"], "device": x["device"] or "Unknown device", "created_at": x["created_at"],
                              "last_used_at": x["last_used_at"], "current": x["id"] == user["session_id"]}
                             for x in s.db.sessions(user["id"])]}  # fmt: skip

    @app.delete("/v1/me/sessions/{sid}")
    def end_session(sid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        sess = s.db.active_session(sid)
        if sess is None or sess["user_id"] != user["id"]:
            raise HTTPException(404, "That device is not signed in.")
        s.db.revoke_session(sid)
        return {"ok": True}

    @app.post("/v1/me/sessions/revoke-others")
    def end_other_sessions(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"ended": s.db.revoke_other_sessions(user["id"], user["session_id"])}

    @app.post("/v1/auth/demo", dependencies=[Depends(rate_limit("demo", 30, 3600))])
    def demo(body: DemoIn, s: Services = Depends(svc)) -> dict:
        if not s.settings.demo_mode:
            raise HTTPException(403, "Guest sign-in is disabled on this server.")
        uname = check_username_valid(body.username, s.db)
        lang = "en-IN"
        if body.language:
            try:
                get_language(body.language)
                lang = body.language
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        user = s.db.create_user(body.display_name.strip(), None, None, is_demo=True, username=uname, language=lang)
        return session(user, s, body.device)

    class MeIn(BaseModel):
        allow_calls: str | None = Field(default=None, pattern="^(everyone|contacts)$")
        read_receipts: bool | None = None
        chat_retention_days: int | None = Field(default=None)
        display_name: str | None = Field(default=None, max_length=60)
        language: str | None = None
        username: str | None = None
        avatar: str | None = Field(default=None, max_length=64)
        phone_hash: str | None = None

    @app.get("/v1/me")
    def me(user: dict = Depends(current_user)) -> dict:
        return public_user(user)

    @app.patch("/v1/me")
    def update_me(body: MeIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        uname = None
        if body.username is not None:
            uname = check_username_valid(body.username, s.db, exclude_id=user["id"])
        clean_name = None
        if body.display_name is not None:
            clean_name = body.display_name.strip()
            if not clean_name or len(clean_name) > 60:
                raise HTTPException(422, "Display name must be between 1 and 60 characters.")
        clean_avatar = None
        if body.avatar is not None:
            av = body.avatar.strip()
            if av == "":
                clean_avatar = ""
                s.delete_custom_avatar(user.get("avatar"))
            elif re.fullmatch(r"avatar-\d{2,4}", av):
                clean_avatar = av
                s.delete_custom_avatar(user.get("avatar"))
            else:
                raise HTTPException(422, "Invalid preset avatar id.")
        if body.language:
            try:
                get_language(body.language)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        if body.chat_retention_days is not None and body.chat_retention_days not in (7, 30, 365):
            raise HTTPException(422, "Chat history can be kept for 7, 30 or 365 days.")
        receipts = None if body.read_receipts is None else int(body.read_receipts)
        p_hash = body.phone_hash.strip().lower() if body.phone_hash else None
        return public_user(s.db.update_user(user["id"], display_name=clean_name, language=body.language,
                                            username=uname, avatar=clean_avatar, allow_calls=body.allow_calls,
                                            read_receipts=receipts, chat_retention_days=body.chat_retention_days,
                                            phone_hash=p_hash))  # fmt: skip

    @app.post("/v1/me/avatar", dependencies=[Depends(rate_limit("avatar-upload", 20, 3600))])
    async def upload_avatar(request: Request, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        import io
        from PIL import Image, ImageOps
        raw = bytearray()
        max_bytes = 2 * 1024 * 1024  # 2 MB raw cap
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > max_bytes:
                raise HTTPException(413, "Avatar photo is too large (max 2 MB).")
        if not raw:
            raise HTTPException(422, "No image data uploaded.")
        try:
            with Image.open(io.BytesIO(raw)) as opened:
                im = ImageOps.exif_transpose(opened).convert("RGBA")
                w, h = im.size
                if w < 16 or h < 16:
                    raise HTTPException(422, "Image is too small.")
                side = min(w, h)
                left = (w - side) // 2
                top = int((h - side) * 0.10) if h > w else 0
                sq = im.crop((left, top, left + side, top + side))
                main_im = sq.resize((512, 512), Image.Resampling.LANCZOS) if sq.width != 512 else sq
                thumb_im = sq.resize((128, 128), Image.Resampling.LANCZOS) if sq.width != 128 else sq
                main_bytes = b""
                for q in (86, 78, 68, 56):
                    buf = io.BytesIO()
                    main_im.save(buf, format="WEBP", quality=q, method=6)
                    main_bytes = buf.getvalue()
                    if len(main_bytes) <= 100 * 1024:
                        break
                tbuf = io.BytesIO()
                thumb_im.save(tbuf, format="WEBP", quality=82, method=6)
                thumb_bytes = tbuf.getvalue()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "Unsupported or corrupted image file.") from None

        fid = uuid.uuid4().hex
        (s.avatar_dir / f"{fid}.webp").write_bytes(main_bytes)
        (s.avatar_dir / f"{fid}-thumb.webp").write_bytes(thumb_bytes)
        s.delete_custom_avatar(user.get("avatar"))
        updated = s.db.update_user(user["id"], avatar=f"custom:{fid}")
        return public_user(updated)

    @app.get("/v1/avatars/{fid}")
    def get_custom_avatar(fid: str, thumb: bool = False, _: dict = Depends(current_user), s: Services = Depends(svc)) -> StreamingResponse:
        if not re.fullmatch(r"[0-9a-f]{32}", fid):
            raise HTTPException(404, "Avatar not found.")
        suffix = "-thumb" if thumb else ""
        path = s.avatar_dir / f"{fid}{suffix}.webp"
        if not path.is_file():
            raise HTTPException(404, "Avatar not found.")
        return StreamingResponse(iter([path.read_bytes()]), media_type="image/webp",
                                 headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/v1/users/check-username", dependencies=[Depends(rate_limit("username", 60, 60))])
    def check_username(username: str, s: Services = Depends(svc)) -> dict:
        u = username.strip().lstrip("@")
        if not USERNAME_RE.match(u):
            return {"available": False, "username": u, "reason": "3-24 characters containing only letters, numbers, and underscores."}
        avail = s.db.is_username_available(u)
        return {
            "available": avail,
            "username": u,
            "reason": None if avail else "This username is already taken. Please choose another username."
        }

    @app.get("/v1/users/search", dependencies=[Depends(rate_limit("search", 60, 60))])
    def search_users(q: str = Query(default=""), user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        clean = q.strip().lstrip("@").strip()
        if not clean:
            return {"users": []}
        return {"users": s.db.search_users(clean, current_user_id=user["id"])}

    # --- config -------------------------------------------------------------------------
    @app.get("/v1/admin/usage")
    def admin_usage(x_admin_token: str = Header(default=""), s: Services = Depends(svc)) -> dict:
        """Today's use of the paid speech APIs (no conversation content). Off unless ADMIN_TOKEN is set."""
        want = s.settings.admin_token.get_secret_value()
        if not want or not hmac.compare_digest(x_admin_token.encode(), want.encode()):
            raise HTTPException(401, "Admin token required.")
        return s.meter.report()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/languages")
    def languages() -> dict:
        return {"languages": catalog(), "primary": ["ta-IN", "en-IN"],
                "speed": {"min": 0.85, "max": 1.15, "default": 1.0}}  # fmt: skip

    @app.get("/v1/ice-servers")
    def ice_servers(_: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"ice_servers": s.settings.ice_servers(_["id"]), "turn_configured": bool(s.settings.turn_urls.strip())}

    @app.get("/v1/diagnostics")
    async def diagnostics(_: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        """Checks each provider without spending credits where possible (no audio, no translation)."""
        out: dict[str, Any] = {"server": "ok", "gnani_key_configured": bool(s.settings.gnani_api_key.get_secret_value()),
                               "translator": s.translator.name, "turn_configured": bool(s.settings.turn_urls.strip()),
                               "demo_mode": s.settings.demo_mode}  # fmt: skip
        t0 = time.monotonic()
        try:
            sess = await asyncio.wait_for(s.recognizer.open("ta-IN"), 10)
            await sess.close()
            out["speech_recognition"] = {"ok": True, "ms": int((time.monotonic() - t0) * 1000)}
        except Exception as exc:  # report, never raise
            out["speech_recognition"] = {"ok": False, "error": getattr(exc, "message", type(exc).__name__)}
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get("https://api.mymemory.translated.net/get", params={"q": "ok", "langpair": "en|ta"})
            out["translation"] = {"ok": r.status_code == 200, "ms": int((time.monotonic() - t0) * 1000)}
        except httpx.HTTPError:
            out["translation"] = {"ok": False, "error": "unreachable"}
        return out

    # --- calls --------------------------------------------------------------------------
    class CreateCallIn(BaseModel):
        language: str = "ta-IN"

    class JoinCallIn(BaseModel):
        code: str
        language: str = "en-IN"

    def call_info(cid: str, call: dict) -> dict:
        return {"call_id": cid, "invite_code": call["code"],
                "invite_link": f"https://sarvagyan.app/join/{call['code']}",
                "app_link": f"sarvagyan://join/{call['code']}", "participants": len(call["participants"])}  # fmt: skip

    @app.post("/v1/calls")
    def create_call(body: CreateCallIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        try:
            get_language(body.language)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        s.expire_waiting()
        cid = uuid.uuid4().hex
        code = new_invite_code()
        while code in s.by_code:
            code = new_invite_code()
        s.calls[cid] = {"code": code, "host": user["id"], "participants": {user["id"]: body.language}, "created": time.time()}
        s.by_code[code] = cid
        s.db.insert_call(cid, code, user["id"])
        s.db.add_participant(cid, user["id"], body.language)
        return call_info(cid, s.calls[cid])

    @app.post("/v1/calls/join")
    def join_call(body: JoinCallIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        try:
            get_language(body.language)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        s.expire_waiting()
        code = normalise_invite_code(body.code)
        cid = s.by_code.get(code)
        if cid is None:
            raise HTTPException(404, "That invitation code is not valid or has expired.")
        call = s.calls[cid]
        if "ring" in call or (call.get("direct") and user["id"] not in call["participants"]):
            raise HTTPException(404, "That invitation code is not valid or has expired.")
        if user["id"] not in call["participants"] and len(call["participants"]) >= 2:
            raise HTTPException(409, "This call already has two people.")
        call["participants"][user["id"]] = body.language
        s.db.add_participant(cid, user["id"], body.language)
        return call_info(cid, call)

    # --- contacts, blocking, who can call me -------------------------------------------------
    def contact_out(u: dict) -> dict:
        return {"id": u["id"], "name": u["display_name"], "username": u.get("username"), "language": u["language"],
                "avatar": u.get("avatar"), "is_demo": bool(u["is_demo"])}  # fmt: skip

    class AddContactIn(BaseModel):
        username: str | None = Field(default=None, max_length=40)
        user_id: str | None = Field(default=None, max_length=64)

    @app.get("/v1/contacts")
    def list_contacts(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"contacts": [contact_out(u) for u in s.db.contacts(user["id"])]}

    @app.post("/v1/contacts")
    def add_contact(body: AddContactIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        other = (s.db.get_user_by_username(body.username.strip().lstrip("@")) if body.username
                 else s.db.get_user(body.user_id) if body.user_id else None)  # fmt: skip
        if other is None or s.db.either_blocked(user["id"], other["id"]):
            raise HTTPException(404, "No one with that username.")
        if other["id"] == user["id"]:
            raise HTTPException(422, "That's you.")
        s.db.add_contact(user["id"], other["id"])
        return {"contact": contact_out(other)}

    @app.delete("/v1/contacts/{contact_id}")
    def remove_contact(contact_id: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        s.db.remove_contact(user["id"], contact_id)
        return {"ok": True}

    @app.get("/v1/contacts/blocked")
    def list_blocked(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"contacts": [contact_out(u) for u in s.db.blocked_users(user["id"])]}

    @app.put("/v1/contacts/blocked/{blocked_id}")
    def block_user(blocked_id: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if blocked_id == user["id"] or s.db.get_user(blocked_id) is None:
            raise HTTPException(404, "User not found.")
        s.db.block(user["id"], blocked_id)
        return {"ok": True}

    @app.delete("/v1/contacts/blocked/{blocked_id}")
    def unblock_user(blocked_id: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        s.db.unblock(user["id"], blocked_id)
        return {"ok": True}

    class MatchPhonesIn(BaseModel):
        phone_hashes: list[str] = Field(default_factory=list, max_length=2000)

    @app.post("/v1/contacts/match-phones")
    def match_phones(body: MatchPhonesIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        hashes = [h.strip().lower() for h in body.phone_hashes if len(h.strip()) >= 16]
        matched = s.db.match_phone_hashes(hashes)
        return {
            "matches": [
                {"id": u["id"], "name": u["display_name"], "username": u.get("username"),
                 "language": u.get("language") or "ta-IN", "avatar": u.get("avatar"), "phone_hash": u.get("phone_hash")}
                for u in matched if u["id"] != user["id"]
            ]
        }

    def may_call(caller: dict, callee: dict, s: Services) -> bool:
        if s.db.either_blocked(caller["id"], callee["id"]):
            return False
        return callee.get("allow_calls") == "everyone" or s.db.is_contact(callee["id"], caller["id"])

    # --- direct calls: ring a person, answer, decline, missed ---------------------------------
    class DirectCallIn(BaseModel):
        to: str = Field(min_length=1, max_length=64)
        language: str = "ta-IN"

    class AnswerIn(BaseModel):
        language: str = "en-IN"

    def ringing_call(cid: str, user: dict, s: Services, role: str) -> dict:
        call = s.calls.get(cid)
        ring = call.get("ring") if call else None
        if ring is None or user["id"] != (ring["to"] if role == "callee" else call["host"]):
            raise HTTPException(404, "That call is not ringing any more.")
        return call

    class DeclineIn(BaseModel):
        reason: str = Field(default="declined", pattern="^(declined|busy)$")

    @app.post("/v1/calls/direct", dependencies=[Depends(rate_limit("direct-call", 20, 60))])
    async def call_person(body: DirectCallIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        try:
            get_language(body.language)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        callee = s.db.get_user(body.to)
        if callee is None or callee["id"] == user["id"]:
            raise HTTPException(404, "User not found.")
        if not may_call(user, callee, s):
            raise HTTPException(403, f"{callee['display_name']} only takes calls from their contacts.")
        s.expire_waiting()
        cid = uuid.uuid4().hex
        code = new_invite_code()
        while code in s.by_code:
            code = new_invite_code()
        # Check if callee is already in an active call room or currently ringing
        callee_busy = any(callee["id"] in r.participants for r in s.rooms.values()) or any(
            (c.get("ring") or {}).get("to") == callee["id"] for c in s.calls.values()
        )
        s.db.insert_call(cid, code, user["id"], callee_id=callee["id"])
        s.db.add_participant(cid, user["id"], body.language)
        if callee_busy:
            s.db.mark_ended(cid, 0, outcome="busy")
            log.info("direct call busy call=%s callee=%s", cid[:8], callee["id"][:8])
            await s.notify_user(user["id"], {"type": "call_busy", "call_id": cid, "peer_id": callee["id"],
                                             "peer_name": callee["display_name"]})  # fmt: skip
            await s.emit_call_state(user["id"], cid, "busy", peer_id=callee["id"], peer_name=callee["display_name"])
            return {**call_info(cid, {"code": code, "participants": {user["id"]: body.language}}),
                    "ringing": False, "reachable": True, "call_state": "busy",
                    "peer_id": callee["id"], "peer_name": callee["display_name"]}
        s.calls[cid] = {"code": code, "host": user["id"], "participants": {user["id"]: body.language},
                        "created": time.time(), "ring": {"to": callee["id"], "state": "ringing"}}  # fmt: skip
        s.by_code[code] = cid
        reachable = await s.notify_user(callee["id"], {
            "type": "incoming_call", "call_id": cid, "expires_in": s.settings.ring_timeout_s,
            "from": {"id": user["id"], "name": user["display_name"], "username": user.get("username"),
                     "language": body.language, "avatar": user.get("avatar")}})  # fmt: skip
        if reachable:
            await s.emit_call_state(user["id"], cid, "ringing", peer_id=callee["id"], peer_name=callee["display_name"])
        else:
            await s.emit_call_state(user["id"], cid, "unavailable", peer_id=callee["id"], peer_name=callee["display_name"])
        s.start_ring_timer(cid)
        log.info("direct call ringing call=%s reachable=%s", cid[:8], reachable)
        return {**call_info(cid, s.calls[cid]), "ringing": True, "reachable": reachable,
                "call_state": "ringing" if reachable else "unavailable",
                "peer_id": callee["id"], "peer_name": callee["display_name"]}  # fmt: skip

    @app.post("/v1/calls/{cid}/answer")
    async def answer_call(cid: str, body: AnswerIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        try:
            get_language(body.language)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        call = ringing_call(cid, user, s, "callee")
        call.pop("ring")
        log.info("call state transition call=%s state=accepted callee=%s", cid[:8], user["id"][:8])
        call["participants"][user["id"]] = body.language
        s.db.add_participant(cid, user["id"], body.language)
        await s.notify_user(call["host"], {"type": "call_answered", "call_id": cid})
        await s.emit_call_state(call["host"], cid, "answered", peer_id=user["id"], peer_name=user["display_name"])
        await s.notify_user(user["id"], {"type": "call_cancelled", "call_id": cid, "reason": "answered_elsewhere"},
                            skip_session=user["session_id"])  # fmt: skip
        host = s.db.get_user(call["host"])
        return {**call_info(cid, call), "call_state": "answered", "peer_id": call["host"], "peer_name": host["display_name"] if host else None}

    @app.post("/v1/calls/{cid}/decline")
    async def decline_call(cid: str, body: DeclineIn | None = Body(default=None), user: dict = Depends(current_user),
                           s: Services = Depends(svc)) -> dict:  # fmt: skip
        call = ringing_call(cid, user, s, "callee")
        await s.finish_ring(cid, call, body.reason if body else "declined")
        return {"ok": True}

    @app.post("/v1/calls/{cid}/cancel")
    async def cancel_call(cid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        call = ringing_call(cid, user, s, "caller")
        await s.finish_ring(cid, call, "cancelled")
        return {"ok": True}

    @app.get("/v1/calls/history")
    def history(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        favs = {f["id"] for f in s.db.favourites(user["id"])}
        items = []
        for row in s.db.history(user["id"]):
            dur = int(row["ended_at"] - row["started_at"]) if row["ended_at"] and row["started_at"] else None
            items.append({"call_id": row["id"], "status": row["status"], "outcome": row.get("outcome"),
                          "has_voicemail": bool(row.get("has_voicemail")),
                          "created_at": row["created_at"], "duration_s": dur, "utterances": row["utterances"],
                          "my_language": row["my_language"],
                          "peer": ({"id": row["peer_id"], "name": row["peer_name"], "language": row["peer_language"],
                                    "is_demo": bool(row["peer_is_demo"]), "avatar": row.get("peer_avatar"),
                                    "favourite": row["peer_id"] in favs}
                                   if row["peer_id"] else None)})  # fmt: skip
        return {"calls": items}

    @app.get("/v1/contacts/favourites")
    def favourites(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"contacts": [{"id": f["id"], "name": f["display_name"], "language": f["language"],
                              "avatar": f.get("avatar"), "is_demo": bool(f["is_demo"])} for f in s.db.favourites(user["id"])]}  # fmt: skip

    @app.put("/v1/contacts/favourites/{contact_id}")
    def add_favourite(contact_id: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if not s.db.have_called(user["id"], contact_id):
            raise HTTPException(404, "You can only favourite people you have called.")
        s.db.set_favourite(user["id"], contact_id, True)
        return {"ok": True}

    @app.delete("/v1/contacts/favourites/{contact_id}")
    def remove_favourite(contact_id: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        s.db.set_favourite(user["id"], contact_id, False)
        return {"ok": True}

    # --- voicemail ------------------------------------------------------------------------
    def voicemail_item(v: dict, sent: bool) -> dict:
        other = v["recipient_id"] if sent else v["sender_id"]
        return {"id": v["id"], "status": v["status"], "created_at": v["created_at"], "heard": v["heard_at"] is not None,
                "duration_ms": v["duration_ms"], "source_lang": v["source_lang"], "target_lang": v["target_lang"],
                "original": v["original"], "translation": v["translation"], "error": v["error"],
                "contact": {"id": other, "name": v["other_name"] or "Deleted account", "language": v["other_language"],
                            "avatar": v.get("other_avatar"), "is_demo": bool(v["other_is_demo"])}}  # fmt: skip

    def purge_old(s: Services) -> None:
        s.db.purge_voicemails(time.time() - vm.RETENTION_S)

    @app.post("/v1/voicemails", status_code=202)
    async def send_voicemail(request: Request, to: str = Query(min_length=1, max_length=200),
                             language: str = Query(default="ta-IN"), auto_detect: bool = False,
                             user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:  # fmt: skip
        try:
            get_language(language)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        to = to.strip()
        by_email = "@" in to
        target = s.db.get_user_by_email(to.lower()) if by_email else s.db.get_user(to)
        # by email: anyone who knows the address; by id: only people you have been on a call with
        if target is None or (not by_email and not s.db.have_called(user["id"], target["id"])):
            raise HTTPException(404, "We couldn't find that person. Use their email address, or pick someone you have called.")
        if target["id"] == user["id"]:
            raise HTTPException(422, "You can't send a voicemail to yourself.")
        if s.db.either_blocked(user["id"], target["id"]):
            raise HTTPException(404, "We couldn't find that person. Use their email address, or pick someone you have called.")
        midnight = datetime.combine(date.today(), datetime.min.time()).timestamp()
        if s.db.sent_today(user["id"], midnight) >= s.settings.daily_voicemail_cap:
            raise HTTPException(429, "Daily voicemail limit reached for this account.")
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > vm.MAX_BYTES:
                raise HTTPException(413, f"Voicemail is too long (max {vm.MAX_SECONDS} seconds).")
            chunks.append(chunk)
        pcm = b"".join(chunks)
        pcm = pcm[: len(pcm) - len(pcm) % 2]
        if len(pcm) < vm.MIN_BYTES:
            raise HTTPException(422, "That recording is too short.")
        purge_old(s)
        duration_ms = len(pcm) * 1000 // (vm.SAMPLE_RATE * 2)
        vid = s.db.insert_voicemail(user["id"], target["id"], language, target["language"], duration_ms)
        s.voicemail.submit(vid, pcm, language, auto_detect, target["language"])
        log.info("voicemail accepted id=%s duration_ms=%d", vid[:8], duration_ms)
        return {"id": vid, "status": "processing", "contact": {"id": target["id"], "name": target["display_name"],
                                                              "language": target["language"]}}  # fmt: skip

    @app.get("/v1/voicemails")
    def list_voicemails(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        purge_old(s)
        inbox = [voicemail_item(v, sent=False) for v in s.db.voicemails(user["id"], sent=False)]
        sent = [voicemail_item(v, sent=True) for v in s.db.voicemails(user["id"], sent=True)]
        return {"inbox": inbox, "sent": sent, "unread": sum(1 for v in inbox if not v["heard"])}

    def own_voicemail(vid: str, user: dict, s: Services) -> dict:
        v = s.db.get_voicemail(vid)
        if v is None or user["id"] not in (v["sender_id"], v["recipient_id"]):
            raise HTTPException(404, "That voicemail no longer exists.")
        return v

    @app.get("/v1/voicemails/{vid}/audio")
    async def voicemail_audio(vid: str, user: dict = Depends(current_user), s: Services = Depends(svc)):
        v = own_voicemail(vid, user, s)
        if v["status"] != "ready" or not v["translation"]:
            raise HTTPException(409, "This voicemail is not ready yet.")
        speech = s.voicemail.speech(v["translation"], v["target_lang"])
        try:
            first = await anext(speech)
        except StopAsyncIteration:
            first = b""
        except ProviderError as exc:
            raise HTTPException(502, f"Couldn't create the translated voice: {exc.message}") from None
        if user["id"] == v["recipient_id"]:
            s.db.mark_heard(vid)

        async def body():
            yield first
            try:
                async for chunk in speech:
                    yield chunk
            except ProviderError as exc:
                log.warning("voicemail audio cut short id=%s code=%s", vid[:8], exc.code)

        return StreamingResponse(body(), media_type="application/octet-stream",
                                 headers={"X-Sample-Rate": str(vm.SAMPLE_RATE)})  # fmt: skip

    @app.post("/v1/voicemails/{vid}/heard")
    def voicemail_heard(vid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        v = own_voicemail(vid, user, s)
        if user["id"] == v["recipient_id"]:
            s.db.mark_heard(vid)
        return {"ok": True}

    @app.delete("/v1/voicemails/{vid}")
    def delete_voicemail(vid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        own_voicemail(vid, user, s)
        s.db.delete_voicemail(vid)
        return {"ok": True}

    # --- global chat (1-to-1 and group messaging) ------------------------------------
    class DirectChatIn(BaseModel):
        username: str | None = None
        user_id: str | None = None

    class GroupChatIn(BaseModel):
        name: str = Field(min_length=1, max_length=80)
        member_ids: list[str] = Field(min_length=1)

    class SendMessageIn(BaseModel):
        text: str = Field(min_length=1, max_length=5000)
        language: str | None = None

    @app.get("/v1/chat/conversations")
    def list_conversations(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"conversations": s.db.list_user_conversations(user["id"])}

    @app.post("/v1/chat/direct")
    def start_direct_chat(body: DirectChatIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        other_user = None
        if body.username:
            other_user = s.db.get_user_by_username(body.username)
        elif body.user_id:
            other_user = s.db.get_user(body.user_id)
        if not other_user:
            raise HTTPException(404, "User not found.")
        if other_user["id"] == user["id"]:
            raise HTTPException(400, "Cannot start a chat with yourself.")
        if s.db.either_blocked(user["id"], other_user["id"]):
            raise HTTPException(404, "User not found.")
        conv = s.db.get_or_create_direct_conversation(user["id"], other_user["id"])
        conv["name"] = other_user["display_name"]
        conv["other_user"] = contact_out(other_user)
        return {"conversation": conv}

    @app.post("/v1/chat/groups")
    def create_group(body: GroupChatIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        valid_member_ids = []
        for mid in body.member_ids:
            if mid == user["id"]:
                continue
            u = s.db.get_user(mid) or s.db.get_user_by_username(mid)
            if u and u["id"] not in valid_member_ids:
                valid_member_ids.append(u["id"])
        if not valid_member_ids:
            raise HTTPException(400, "At least one other member is required to create a group.")
        conv = s.db.create_group_conversation(user["id"], body.name.strip(), valid_member_ids)
        return {"conversation": conv}

    @app.get("/v1/chat/conversations/{cid}")
    def get_conversation_details(cid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if not s.db.is_conversation_member(cid, user["id"]):
            raise HTTPException(403, "You are not a member of this conversation.")
        conv = s.db.get_conversation(cid)
        if not conv:
            raise HTTPException(404, "Conversation not found.")
        conv["members"] = s.db.get_conversation_members(cid)
        return {"conversation": conv}

    @app.get("/v1/chat/conversations/{cid}/messages")
    async def get_messages(cid: str, limit: int = 50, before: float | None = None,
                           user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if not s.db.is_conversation_member(cid, user["id"]):
            raise HTTPException(403, "You are not a member of this conversation.")
        if s.db.mark_conversation_read(cid, user["id"]) and user.get("read_receipts", 1):
            await s.notify_members(cid, {"type": "chat_read", "conversation_id": cid, "user_id": user["id"]},
                                   except_user=user["id"])  # fmt: skip
        hidden = s.db.hidden_message_ids(user["id"], cid)
        raw_msgs = [m for m in s.db.get_messages(cid, limit=limit, before=before) if m["id"] not in hidden]
        others = s.db.receipts(cid, user["id"])
        share_reads = bool(user.get("read_receipts", 1))

        def status(m: dict) -> str | None:
            if m["sender_id"] != user["id"] or not others:
                return None
            # read receipts work both ways: if I hide mine, I don't see others'
            if share_reads and all(o["read_receipts"] and o["last_read_at"] >= m["created_at"] for o in others):
                return "read"
            if all(max(o["last_delivered_at"], o["last_read_at"]) >= m["created_at"] for o in others):
                return "delivered"
            return "sent"
        target_lang = user.get("language") or "en-IN"
        target_base = target_lang.split("-")[0].lower()

        out = []
        for msg in raw_msgs:
            if msg.get("deleted_at"):
                out.append({**{k: msg[k] for k in ("id", "conversation_id", "sender_id", "sender_name", "source_lang",
                                                   "created_at")},
                            "original_text": "", "translated_text": "", "is_translated": False, "deleted": True,
                            "status": status(msg)})  # fmt: skip
                continue
            orig = msg.get("original_text") or ""
            src_lang = msg.get("source_lang") or "en-IN"
            src_base = src_lang.split("-")[0].lower()
            trans = orig
            is_trans = False

            if orig and orig != "[Voice Message]" and target_base != src_base:
                cached = s.db.get_cached_translation(msg["id"], target_lang)
                if cached:
                    trans = cached
                    is_trans = (trans != orig)
                else:
                    try:
                        trans = await s.translator.translate(orig, src_lang, target_lang)
                        s.db.store_cached_translation(msg["id"], target_lang, trans)
                        is_trans = (trans != orig)
                    except Exception as exc:
                        log.warning("get_messages translation error: %s", exc)
                        trans = orig

            item = dict(msg)
            item.pop("expires_at", None)
            item.pop("deleted_at", None)
            item["translated_text"] = trans
            item["is_translated"] = is_trans
            item["status"] = status(msg)
            if item.get("audio_id"):
                item["audio_url"] = f"/v1/chat/audio/{item['audio_id']}"
            out.append(item)

        return {"messages": out}

    @app.post("/v1/chat/conversations/{cid}/messages")
    async def send_message(cid: str, body: SendMessageIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if not s.db.is_conversation_member(cid, user["id"]):
            raise HTTPException(403, "You are not a member of this conversation.")
        text = body.text.strip()
        if not text:
            raise HTTPException(422, "Message text cannot be empty.")
        src_lang = body.language or user.get("language") or "en-IN"
        msg = s.db.insert_message(cid, user["id"], user["display_name"], src_lang, text)
        await s.broadcast_chat_message(cid, msg)
        return {"message": msg}

    @app.post("/v1/chat/conversations/{cid}/voice")
    async def send_voice_message(cid: str, req: Request, language: str = Query("ta-IN"),
                                 tag: str | None = Query(default=None, pattern="^(voicemail)$"),
                                 user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if not s.db.is_conversation_member(cid, user["id"]):
            raise HTTPException(403, "You are not a member of this conversation.")
        is_gzip = (req.headers.get("content-encoding") or "").lower() == "gzip" or (
            req.headers.get("x-audio-encoding") or ""
        ).lower() == "gzip"
        chunks: list[bytes] = []
        size = 0
        async for chunk in req.stream():
            size += len(chunk)
            if size > vm.MAX_BYTES:
                raise HTTPException(413, "Voice message exceeds the 60-second limit.")
            chunks.append(chunk)
        raw_bytes = b"".join(chunks)
        if is_gzip:
            try:
                pcm = gzip.decompress(raw_bytes)
            except Exception:
                raise HTTPException(400, "Invalid compressed audio payload.") from None
            if len(pcm) > vm.MAX_BYTES:
                raise HTTPException(413, "Voice message exceeds the 60-second limit.")
        else:
            pcm = raw_bytes
        pcm = pcm[: len(pcm) - len(pcm) % 2]
        if len(pcm) < vm.MIN_BYTES:
            raise HTTPException(422, "Voice message is too short.")

        audio_id = uuid.uuid4().hex
        audio_file = s.chat_audio_dir / f"{audio_id}.pcm"
        audio_file.write_bytes(pcm)
        duration_ms = int(len(pcm) / (vm.SAMPLE_RATE * 2) * 1000)

        msg = s.db.insert_message(cid, user["id"], user["display_name"], language, "[Voice Message]",
                                  audio_id=audio_id, duration_ms=duration_ms, tag=tag)
        msg["audio_url"] = f"/v1/chat/audio/{audio_id}"
        await s.broadcast_chat_message(cid, msg)
        s._spawn_bg(s.process_voice_transcript(cid, msg["id"], pcm, language))
        return {"message": msg}

    @app.delete("/v1/chat/messages/{mid}")
    async def delete_message(mid: str, scope: str = Query(default="me", pattern="^(me|everyone)$"),
                             user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:  # fmt: skip
        msg = s.db.get_message(mid)
        if msg is None or not s.db.is_conversation_member(msg["conversation_id"], user["id"]):
            raise HTTPException(404, "Message not found.")
        if scope == "me":
            s.db.hide_message(user["id"], mid)
            return {"ok": True}
        if msg["sender_id"] != user["id"]:
            raise HTTPException(403, "Only the sender can delete a message for everyone.")
        audio_id = s.db.delete_message_for_everyone(mid)
        if audio_id:
            with contextlib.suppress(OSError):
                (s.chat_audio_dir / f"{audio_id}.pcm").unlink(missing_ok=True)
        await s.notify_members(msg["conversation_id"], {"type": "message_deleted", "conversation_id":
                                                        msg["conversation_id"], "message_id": mid})  # fmt: skip
        return {"ok": True}

    @app.get("/v1/chat/audio/{audio_id}")
    def get_chat_audio(audio_id: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> StreamingResponse:
        # only members of the conversation the voice message belongs to may play it
        conv_id = s.db.conversation_of_audio(audio_id) if re.fullmatch(r"[0-9a-f]{32}", audio_id) else None
        if conv_id is None or not s.db.is_conversation_member(conv_id, user["id"]):
            raise HTTPException(404, "Audio file not found.")
        audio_file = s.chat_audio_dir / f"{audio_id}.pcm"
        if not audio_file.is_file():
            raise HTTPException(404, "Audio file not found.")
        data = audio_file.read_bytes()
        return StreamingResponse(iter([data]), media_type="application/octet-stream",
                                 headers={"X-Sample-Rate": str(vm.SAMPLE_RATE)})

    @app.get("/v1/chat/messages/{mid}/translated-audio")
    async def get_chat_translated_audio(mid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> StreamingResponse:
        msg = s.db.get_message(mid)
        if msg is None or msg.get("deleted_at") or not s.db.is_conversation_member(msg["conversation_id"], user["id"]):
            raise HTTPException(404, "Message not found.")
        orig = (msg.get("original_text") or "").strip()
        if not orig or orig == "[Voice Message]":
            raise HTTPException(422, "No transcript available to speak for this voice message.")
        src_lang = msg.get("source_lang") or "en-IN"
        target_lang = user.get("language") or "en-IN"
        if target_lang.split("-")[0].lower() == src_lang.split("-")[0].lower():
            text_to_speak = orig
        else:
            cached = s.db.get_cached_translation(mid, target_lang)
            if cached:
                text_to_speak = cached
            else:
                text_to_speak = await s.translator.translate(orig, src_lang, target_lang)
                s.db.store_cached_translation(mid, target_lang, text_to_speak)
        from sarvagyan_server.languages import voice_for
        voice = voice_for(target_lang, None)
        cache_key = s.tts_cache.key(text_to_speak, target_lang, voice, 1.0)
        cached_pcm = s.tts_cache.get(cache_key)
        if cached_pcm is not None:
            return StreamingResponse(iter(cached_pcm), media_type="application/octet-stream",
                                     headers={"X-Sample-Rate": str(vm.SAMPLE_RATE)})
        synth = s.synthesizer_factory()
        chunks: list[bytes] = []
        try:
            async for chunk in synth.synthesize(text_to_speak, target_lang, voice, 1.0):
                chunks.append(chunk)
        finally:
            close_fn = getattr(synth, "close", None)
            if close_fn is not None:
                res = close_fn()
                if inspect.isawaitable(res):
                    await res
        if chunks:
            s.tts_cache.put(cache_key, chunks)
        return StreamingResponse(iter(chunks), media_type="application/octet-stream",
                                 headers={"X-Sample-Rate": str(vm.SAMPLE_RATE)})

    @app.post("/v1/chat/conversations/{cid}/members")
    def add_member(cid: str, body: dict, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        role = s.db.get_member_role(cid, user["id"])
        if role != "admin":
            raise HTTPException(403, "Only admins can add members to this group.")
        target_uid = body.get("user_id")
        if not target_uid and body.get("username"):
            tu = s.db.get_user_by_username(body["username"])
            target_uid = tu["id"] if tu else None
        if not target_uid or not s.db.get_user(target_uid) or s.db.either_blocked(user["id"], target_uid):
            raise HTTPException(404, "User not found.")
        s.db.add_conversation_member(cid, target_uid, role="member")
        return {"ok": True}

    @app.delete("/v1/chat/conversations/{cid}/members/{uid}")
    def remove_member(cid: str, uid: str, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        role = s.db.get_member_role(cid, user["id"])
        if user["id"] != uid and role != "admin":
            raise HTTPException(403, "Only admins can remove members.")
        s.db.remove_conversation_member(cid, uid)
        return {"ok": True}

    @app.websocket("/v1/chat/ws")
    async def chat_socket(ws: WebSocket) -> None:
        s: Services = app.state.services
        # the token comes only in the Authorization header, never in the URL (URLs end up in logs)
        auth_token = (ws.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        user = s.user_for_token(auth_token)
        if user is None:
            await ws.close(code=4401, reason="unauthorized")
            return
        await ws.accept()
        ws.session_id = user["session_id"]
        s.chat_sockets[user["id"]].add(ws)
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                text = msg.get("text") or ""
                if not text:
                    continue
                try:
                    event = json.loads(text)
                except Exception:
                    continue
                kind = event.get("type")
                if kind == "typing":
                    cid = event.get("conversation_id")
                    if cid and s.db.is_conversation_member(cid, user["id"]):
                        await s.broadcast_chat_typing(cid, user["id"], user["display_name"])
                elif kind == "chat_focus":
                    cid = event.get("conversation_id")
                    if cid and s.db.is_conversation_member(cid, user["id"]):
                        s.active_chats[ws] = cid
                    else:
                        s.active_chats.pop(ws, None)
                elif kind == "call_ack":
                    cid = str(event.get("call_id") or "")
                    state = str(event.get("state") or "")
                    ack_id = event.get("ack_id")
                    if cid and state:
                        s.ack_call_state(user["id"], cid, state, str(ack_id) if ack_id else None)
                        await ws.send_text(json.dumps({"type": "call_ack_received", "call_id": cid, "state": state, "ack_id": ack_id}))
                elif kind == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": event.get("t")}))
        except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
            pass
        finally:
            s.active_chats.pop(ws, None)
            s.chat_sockets[user["id"]].discard(ws)
            with contextlib.suppress(Exception):
                await ws.close()

    # --- live call socket ----------------------------------------------------------------
    @app.websocket("/v1/calls/{call_id}/ws")
    async def call_socket(ws: WebSocket, call_id: str) -> None:
        s: Services = app.state.services
        auth_token = (ws.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        user = s.user_for_token(auth_token)
        call = s.calls.get(call_id)
        if user is None:
            await ws.close(code=4401, reason="unauthorized")
            return
        if call is None or user["id"] not in call["participants"]:
            await ws.close(code=4404, reason="call not found or not invited")
            return
        await ws.accept()

        async def send(item: dict | bytes) -> None:
            if isinstance(item, bytes):
                await ws.send_bytes(item)
            else:
                await ws.send_text(json.dumps(item, ensure_ascii=False))

        room = s.room(call_id)
        part: Participant | None = None
        leaving = False
        try:
            first = json.loads(await asyncio.wait_for(ws.receive_text(), 10))
            if first.get("type") != "hello":
                await ws.close(code=4400, reason="expected hello")
                return
            part = Participant(user_id=user["id"], name=user["display_name"],
                               language=call["participants"][user["id"]], avatar=user.get("avatar"))  # fmt: skip
            try:
                part.apply({k: v for k, v in first.items() if k != "type"})
            except ValueError as exc:
                await send({"type": "error", "scope": "call", "code": "unsupported_language", "message": str(exc),
                            "retryable": False})  # fmt: skip
            await room.connect(part, send)
            await send({"type": "ice_servers", "ice_servers": s.settings.ice_servers(user["id"])})
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if (data := msg.get("bytes")) is not None:
                    if len(data) <= MAX_FRAME:
                        pipe = room.pipelines.get(user["id"])
                        if pipe is not None:
                            pipe.feed(data)
                    continue
                text = msg.get("text") or ""
                if len(text) > MAX_WS_TEXT:
                    continue
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "leave":
                    leaving = True
                    break
                await handle(room, part, event, send)
        except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
            pass
        except PermissionError as exc:
            with contextlib.suppress(Exception):
                await send({"type": "error", "scope": "call", "code": "full", "message": str(exc), "retryable": False})
        finally:
            if part is not None:
                await room.disconnect(user["id"], leaving=leaving)
                if room.is_empty():
                    await s.end_room(call_id)
            with contextlib.suppress(Exception):
                await ws.close()

    async def handle(room: CallRoom, part: Participant, msg: dict, send) -> None:
        kind = msg.get("type")
        if kind == "signal":
            if not await room.relay_signal(part.user_id, msg.get("payload")):
                await send({"type": "notice", "code": "peer_unavailable", "message": "The other person is not connected yet."})
        elif kind == "settings":
            old_lang, old_auto = part.language, part.auto_detect
            try:
                part.apply({k: v for k, v in msg.items() if k != "type"})
            except ValueError as exc:
                await send({"type": "error", "scope": "call", "code": "unsupported_language", "message": str(exc),
                            "retryable": False})  # fmt: skip
                return
            if (part.language, part.auto_detect) != (old_lang, old_auto) and (pipe := room.pipelines.get(part.user_id)):
                await pipe.set_language()
            await room.broadcast({"type": "participant", "participant": part.public()})
            if part.language != old_lang:
                from sarvagyan_server.languages import get_language
                new_lang_name = get_language(part.language).name
                for other_id, other_part in room.participants.items():
                    if other_id != part.user_id:
                        await room.send(other_part, {
                            "type": "notice",
                            "code": "language_switched",
                            "message": f"{part.name} switched to {new_lang_name}",
                        })
        elif kind == "retry":
            await room.retry(str(msg.get("id", "")))
        elif kind == "ping":
            await send({"type": "pong", "t": msg.get("t")})

    return app


app = create_app()
