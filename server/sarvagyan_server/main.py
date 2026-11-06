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
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
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
from sarvagyan_server.realtime import CallRoom, Participant
from sarvagyan_server import voicemail as vm
from sarvagyan_server.security import hash_password, issue_token, new_invite_code, normalise_invite_code, verify_password, verify_token

log = logging.getLogger("sarvagyan")
WAITING_TTL_S = 15 * 60
MAX_WS_TEXT = 64 * 1024
MAX_FRAME = 4096


class Services:
    """Everything stateful, created once per app (tests inject fakes)."""

    def __init__(self, settings: Settings, db: Database | None = None, recognizer=None, translator=None,
                 synthesizer_factory=None, voicemail_pace_s: float = vm.FRAME_S) -> None:  # fmt: skip
        self.settings = settings
        self.db = db or Database(settings.data_path / "sarvagyan.sqlite3")
        key = settings.gnani_api_key.get_secret_value()
        self.recognizer = recognizer or GnaniRecognizer(key, settings.gnani_stt_url, settings.stt_model)
        self.translator = translator or MyMemoryTranslator(settings.mymemory_email)
        self.synthesizer_factory = synthesizer_factory or (
            lambda: GnaniSynthesizer(key, settings.gnani_tts_url, settings.tts_model))
        self.voicemail = vm.VoicemailService(self.db, self.recognizer, self.translator, self.synthesizer_factory,
                                             pace_s=voicemail_pace_s)  # fmt: skip
        self.rooms: dict[str, CallRoom] = {}
        self.calls: dict[str, dict] = {}  # call_id -> {code, host, participants{uid: language}, created}
        self.by_code: dict[str, str] = {}
        self._usage: dict[tuple[str, str], int] = defaultdict(int)
        self.chat_audio_dir = self.settings.data_path / "chat_audio"
        self.chat_audio_dir.mkdir(parents=True, exist_ok=True)
        self.chat_sockets: dict[str, set[WebSocket]] = defaultdict(set)

    async def broadcast_chat_message(self, cid: str, msg: dict) -> None:
        members = self.db.get_conversation_members(cid)
        for m in members:
            uid = m.get("id") or m.get("user_id")
            socks = self.chat_sockets.get(uid)
            if not socks:
                continue
            target_lang = m.get("language") or "en-IN"
            source_lang = msg.get("source_lang") or "en-IN"
            orig_text = msg.get("original_text") or ""
            translated_text = orig_text
            is_translated = False

            target_base = target_lang.split("-")[0].lower()
            source_base = source_lang.split("-")[0].lower()

            if orig_text and target_base != source_base:
                cached = self.db.get_cached_translation(msg["id"], target_lang)
                if cached:
                    translated_text = cached
                    is_translated = (translated_text != orig_text)
                else:
                    try:
                        translated_text = await self.translator.translate(orig_text, source_lang, target_lang)
                        self.db.store_cached_translation(msg["id"], target_lang, translated_text)
                        is_translated = (translated_text != orig_text)
                    except Exception as exc:
                        log.warning("broadcast translation failed: %s", exc)
                        translated_text = orig_text

            payload = {
                "type": "message",
                "conversation_id": cid,
                "message": {
                    "id": msg["id"],
                    "conversation_id": cid,
                    "sender_id": msg["sender_id"],
                    "sender_name": msg["sender_name"],
                    "source_lang": source_lang,
                    "original_text": orig_text,
                    "translated_text": translated_text,
                    "is_translated": is_translated,
                    "audio_id": msg.get("audio_id"),
                    "duration_ms": msg.get("duration_ms"),
                    "created_at": msg["created_at"],
                }
            }
            raw = json.dumps(payload, ensure_ascii=False)
            dead = set()
            for ws in list(socks):
                try:
                    await ws.send_text(raw)
                except Exception:
                    dead.add(ws)
            socks.difference_update(dead)

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

    def quota(self, user_id: str) -> bool:
        key = (user_id, date.today().isoformat())
        self._usage[key] += 1
        return self._usage[key] <= self.settings.daily_utterance_cap

    def room(self, call_id: str) -> CallRoom:
        if call_id not in self.rooms:
            self.rooms[call_id] = CallRoom(call_id, self.recognizer, self.translator, self.synthesizer_factory,
                                           on_started=self.db.mark_started, quota=self.quota,
                                           on_empty=lambda: self.end_room(call_id))  # fmt: skip
        return self.rooms[call_id]

    async def end_room(self, call_id: str) -> None:
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
        yield
        for cid in list(app.state.services.rooms):
            await app.state.services.end_room(cid)
        await app.state.services.voicemail.close()

    app = FastAPI(title="Sarvagyan API", version=__version__, lifespan=lifespan)
    if services is not None:
        app.state.services = services
    app.add_middleware(CORSMiddleware, allow_origins=[], allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"])

    def svc() -> Services:
        return app.state.services

    def current_user(authorization: str = Header(default=""), s: Services = Depends(svc)) -> dict:
        token = authorization.removeprefix("Bearer ").strip()
        uid = verify_token(token, s.settings.signing_key) if token else None
        user = s.db.get_user(uid) if uid else None
        if user is None:
            raise HTTPException(401, "Please sign in again.")
        return user

    def public_user(u: dict) -> dict:
        return {"id": u["id"], "display_name": u["display_name"], "username": u.get("username"), "email": u["email"],
                "is_demo": bool(u["is_demo"]), "language": u["language"]}  # fmt: skip

    def session(u: dict, s: Services) -> dict:
        return {"token": issue_token(u["id"], s.settings.signing_key), "user": public_user(u)}

    USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,24}$")

    def check_username_valid(u: str | None, db: Database, exclude_id: str | None = None) -> str | None:
        if not u:
            return None
        cleaned = u.strip()
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

    class LoginIn(BaseModel):
        email: str
        password: str

    class DemoIn(BaseModel):
        display_name: str = Field(min_length=1, max_length=60)
        username: str | None = None

    @app.post("/v1/auth/register")
    def register(body: RegisterIn, s: Services = Depends(svc)) -> dict:
        email = body.email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(422, "Enter a valid email address.")
        if s.db.get_user_by_email(email):
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        uname = check_username_valid(body.username, s.db)
        user = s.db.create_user(body.display_name.strip(), email, hash_password(body.password), is_demo=False, username=uname)
        return session(user, s)

    @app.post("/v1/auth/login")
    def login(body: LoginIn, s: Services = Depends(svc)) -> dict:
        user = s.db.get_user_by_email(body.email.strip().lower())
        if user is None or not user["password_hash"] or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Email or password is incorrect.")
        return session(user, s)

    @app.post("/v1/auth/demo")
    def demo(body: DemoIn, s: Services = Depends(svc)) -> dict:
        if not s.settings.demo_mode:
            raise HTTPException(403, "Guest sign-in is disabled on this server.")
        uname = check_username_valid(body.username, s.db)
        user = s.db.create_user(body.display_name.strip(), None, None, is_demo=True, username=uname)
        return session(user, s)

    class MeIn(BaseModel):
        display_name: str | None = Field(default=None, max_length=60)
        language: str | None = None
        username: str | None = None

    @app.get("/v1/me")
    def me(user: dict = Depends(current_user)) -> dict:
        return public_user(user)

    @app.patch("/v1/me")
    def update_me(body: MeIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        uname = None
        if body.username is not None:
            uname = check_username_valid(body.username, s.db, exclude_id=user["id"])
        if body.language:
            try:
                get_language(body.language)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        return public_user(s.db.update_user(user["id"], display_name=body.display_name, language=body.language, username=uname))

    @app.get("/v1/users/check-username")
    def check_username(username: str, s: Services = Depends(svc)) -> dict:
        u = username.strip()
        if not USERNAME_RE.match(u):
            return {"available": False, "username": u, "reason": "3-24 characters (letters, numbers, underscores)"}
        return {"available": s.db.is_username_available(u), "username": u}

    @app.get("/v1/users/search")
    def search_users(q: str = Query(min_length=1), user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"users": s.db.search_users(q, current_user_id=user["id"])}

    # --- config -------------------------------------------------------------------------
    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/languages")
    def languages() -> dict:
        return {"languages": catalog(), "primary": ["ta-IN", "en-IN"],
                "speed": {"min": 0.85, "max": 1.15, "default": 1.0}}  # fmt: skip

    @app.get("/v1/ice-servers")
    def ice_servers(_: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"ice_servers": s.settings.ice_servers(), "turn_configured": bool(s.settings.turn_urls.strip())}

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
        if user["id"] not in call["participants"] and len(call["participants"]) >= 2:
            raise HTTPException(409, "This call already has two people.")
        call["participants"][user["id"]] = body.language
        s.db.add_participant(cid, user["id"], body.language)
        return call_info(cid, call)

    @app.get("/v1/calls/history")
    def history(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        favs = {f["id"] for f in s.db.favourites(user["id"])}
        items = []
        for row in s.db.history(user["id"]):
            dur = int(row["ended_at"] - row["started_at"]) if row["ended_at"] and row["started_at"] else None
            items.append({"call_id": row["id"], "status": row["status"], "created_at": row["created_at"],
                          "duration_s": dur, "utterances": row["utterances"], "my_language": row["my_language"],
                          "peer": ({"id": row["peer_id"], "name": row["peer_name"], "language": row["peer_language"],
                                    "is_demo": bool(row["peer_is_demo"]), "favourite": row["peer_id"] in favs}
                                   if row["peer_id"] else None)})  # fmt: skip
        return {"calls": items}

    @app.get("/v1/contacts/favourites")
    def favourites(user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        return {"contacts": [{"id": f["id"], "name": f["display_name"], "language": f["language"],
                              "is_demo": bool(f["is_demo"])} for f in s.db.favourites(user["id"])]}  # fmt: skip

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
                            "is_demo": bool(v["other_is_demo"])}}  # fmt: skip

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
        conv = s.db.get_or_create_direct_conversation(user["id"], other_user["id"])
        conv["name"] = other_user["display_name"]
        conv["other_user"] = public_user(other_user)
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
        s.db.mark_conversation_read(cid, user["id"])
        raw_msgs = s.db.get_messages(cid, limit=limit, before=before)
        target_lang = user.get("language") or "en-IN"
        target_base = target_lang.split("-")[0].lower()

        out = []
        for msg in raw_msgs:
            orig = msg.get("original_text") or ""
            src_lang = msg.get("source_lang") or "en-IN"
            src_base = src_lang.split("-")[0].lower()
            trans = orig
            is_trans = False

            if orig and target_base != src_base:
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
            item["translated_text"] = trans
            item["is_translated"] = is_trans
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
                                 user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if not s.db.is_conversation_member(cid, user["id"]):
            raise HTTPException(403, "You are not a member of this conversation.")
        pcm = await req.body()
        if len(pcm) < vm.MIN_BYTES:
            raise HTTPException(422, "Voice message is too short.")
        if len(pcm) > vm.MAX_BYTES:
            raise HTTPException(422, "Voice message exceeds the 60-second limit.")

        audio_id = uuid.uuid4().hex
        audio_file = s.chat_audio_dir / f"{audio_id}.pcm"
        audio_file.write_bytes(pcm)
        duration_ms = int(len(pcm) / (vm.SAMPLE_RATE * 2) * 1000)

        transcribed_text = ""
        detected_lang = language
        try:
            transcribed_text, detected = await vm.transcribe(s.recognizer, pcm, language)
            if detected:
                detected_lang = detected
        except Exception as exc:
            log.warning("chat voice transcription error: %s", exc)

        if not transcribed_text:
            transcribed_text = "[Voice Message]"

        msg = s.db.insert_message(cid, user["id"], user["display_name"], detected_lang, transcribed_text,
                                  audio_id=audio_id, duration_ms=duration_ms)
        await s.broadcast_chat_message(cid, msg)
        return {"message": msg}

    @app.get("/v1/chat/audio/{audio_id}")
    def get_chat_audio(audio_id: str, s: Services = Depends(svc)) -> StreamingResponse:
        audio_file = s.chat_audio_dir / f"{audio_id}.pcm"
        if not audio_file.is_file():
            raise HTTPException(404, "Audio file not found.")
        data = audio_file.read_bytes()
        return StreamingResponse(iter([data]), media_type="application/octet-stream",
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
        if not target_uid or not s.db.get_user(target_uid):
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
        token = (ws.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        if not token:
            token = ws.query_params.get("token", "")
        uid = verify_token(token, s.settings.signing_key) if token else None
        user = s.db.get_user(uid) if uid else None
        if user is None:
            await ws.close(code=4401, reason="unauthorized")
            return
        await ws.accept()
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
                elif kind == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": event.get("t")}))
        except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
            pass
        finally:
            s.chat_sockets[user["id"]].discard(ws)
            with contextlib.suppress(Exception):
                await ws.close()

    # --- live call socket ----------------------------------------------------------------
    @app.websocket("/v1/calls/{call_id}/ws")
    async def call_socket(ws: WebSocket, call_id: str) -> None:
        s: Services = app.state.services
        token = (ws.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        uid = verify_token(token, s.settings.signing_key) if token else None
        user = s.db.get_user(uid) if uid else None
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
                               language=call["participants"][user["id"]])  # fmt: skip
            try:
                part.apply({k: v for k, v in first.items() if k != "type"})
            except ValueError as exc:
                await send({"type": "error", "scope": "call", "code": "unsupported_language", "message": str(exc),
                            "retryable": False})  # fmt: skip
            await room.connect(part, send)
            await send({"type": "ice_servers", "ice_servers": s.settings.ice_servers()})
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
        elif kind == "retry":
            await room.retry(str(msg.get("id", "")))
        elif kind == "ping":
            await send({"type": "pong", "t": msg.get("t")})

    return app


app = create_app()
