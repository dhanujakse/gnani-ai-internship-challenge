"""Sarvagyan API.

    cd server && uv run uvicorn sarvagyan_server.main:app --host 0.0.0.0 --port 8787

REST (JSON, Bearer token):
  POST /v1/auth/register | /v1/auth/login | /v1/auth/demo      GET/PATCH /v1/me
  GET  /v1/languages   GET /v1/ice-servers   GET /v1/diagnostics
  POST /v1/calls  -> {call_id, invite_code, invite_link}       POST /v1/calls/join {code}
  GET  /v1/calls/history   GET/PUT/DELETE /v1/contacts/favourites[/{id}]
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
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sarvagyan_server import __version__
from sarvagyan_server.config import Settings, get_settings
from sarvagyan_server.db import Database
from sarvagyan_server.languages import catalog, get_language
from sarvagyan_server.providers.gnani_stt import GnaniRecognizer
from sarvagyan_server.providers.gnani_tts import GnaniSynthesizer
from sarvagyan_server.providers.mymemory import MyMemoryTranslator
from sarvagyan_server.realtime import CallRoom, Participant
from sarvagyan_server.security import hash_password, issue_token, new_invite_code, normalise_invite_code, verify_password, verify_token

log = logging.getLogger("sarvagyan")
WAITING_TTL_S = 15 * 60
MAX_WS_TEXT = 64 * 1024
MAX_FRAME = 4096


class Services:
    """Everything stateful, created once per app (tests inject fakes)."""

    def __init__(self, settings: Settings, db: Database | None = None, recognizer=None, translator=None,
                 synthesizer_factory=None) -> None:  # fmt: skip
        self.settings = settings
        self.db = db or Database(settings.data_path / "sarvagyan.sqlite3")
        key = settings.gnani_api_key.get_secret_value()
        self.recognizer = recognizer or GnaniRecognizer(key, settings.gnani_stt_url, settings.stt_model)
        self.translator = translator or MyMemoryTranslator(settings.mymemory_email)
        self.synthesizer_factory = synthesizer_factory or (
            lambda: GnaniSynthesizer(key, settings.gnani_tts_url, settings.tts_model))
        self.rooms: dict[str, CallRoom] = {}
        self.calls: dict[str, dict] = {}  # call_id -> {code, host, participants{uid: language}, created}
        self.by_code: dict[str, str] = {}
        self._usage: dict[tuple[str, str], int] = defaultdict(int)

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

    app = FastAPI(title="Sarvagyan API", version=__version__, lifespan=lifespan)
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
        return {"id": u["id"], "display_name": u["display_name"], "email": u["email"],
                "is_demo": bool(u["is_demo"]), "language": u["language"]}  # fmt: skip

    def session(u: dict, s: Services) -> dict:
        return {"token": issue_token(u["id"], s.settings.signing_key), "user": public_user(u)}

    # --- auth -------------------------------------------------------------------------
    class RegisterIn(BaseModel):
        email: str = Field(min_length=3, max_length=200)
        password: str = Field(min_length=8, max_length=200)
        display_name: str = Field(min_length=1, max_length=60)

    class LoginIn(BaseModel):
        email: str
        password: str

    class DemoIn(BaseModel):
        display_name: str = Field(min_length=1, max_length=60)

    @app.post("/v1/auth/register")
    def register(body: RegisterIn, s: Services = Depends(svc)) -> dict:
        email = body.email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(422, "Enter a valid email address.")
        if s.db.get_user_by_email(email):
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        user = s.db.create_user(body.display_name.strip(), email, hash_password(body.password), is_demo=False)
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
        user = s.db.create_user(body.display_name.strip(), None, None, is_demo=True)
        return session(user, s)

    class MeIn(BaseModel):
        display_name: str | None = Field(default=None, max_length=60)
        language: str | None = None

    @app.get("/v1/me")
    def me(user: dict = Depends(current_user)) -> dict:
        return public_user(user)

    @app.patch("/v1/me")
    def update_me(body: MeIn, user: dict = Depends(current_user), s: Services = Depends(svc)) -> dict:
        if body.language:
            try:
                get_language(body.language)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        return public_user(s.db.update_user(user["id"], display_name=body.display_name, language=body.language))

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
