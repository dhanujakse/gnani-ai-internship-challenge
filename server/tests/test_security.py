"""Phase 1 security: revocable sessions, refresh-token rotation, rate limits, auth on every route, retention."""

import time

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.websockets import WebSocketDisconnect

from sarvagyan_server.security import issue_token


def register(env, email="siva@example.com", device="Pixel 8"):
    r = env.client.post("/v1/auth/register", json={"email": email, "password": "longpassword",
                                                   "display_name": "Siva", "device": device})  # fmt: skip
    assert r.status_code == 200, r.text
    return r.json()


def login(env, email="siva@example.com", password="longpassword", device="Phone 2"):
    return env.client.post("/v1/auth/login", json={"email": email, "password": password, "device": device})


def me(env, token):
    return env.client.get("/v1/me", headers=env.auth(token)).status_code


def test_sign_in_returns_short_access_token_and_refresh_token(env) -> None:
    body = register(env)
    assert body["refresh_token"] and body["expires_in"] == 900
    assert me(env, body["token"]) == 200


def test_refresh_rotates_and_a_reused_refresh_token_ends_the_session(env) -> None:
    first = register(env)
    r = env.client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"] and me(env, second["token"]) == 200
    # the old refresh token is presented again (stolen copy): the whole session ends
    assert env.client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert me(env, second["token"]) == 401
    assert env.client.post("/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_unknown_refresh_token_is_rejected(env) -> None:
    assert env.client.post("/v1/auth/refresh", json={"refresh_token": "x" * 43}).status_code == 401


def test_logout_ends_the_session_immediately(env) -> None:
    body = register(env)
    assert env.client.post("/v1/auth/logout", headers=env.auth(body["token"])).status_code == 200
    assert me(env, body["token"]) == 401
    assert env.client.post("/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401


def test_devices_list_and_sign_out_everywhere_else(env) -> None:
    a = register(env, device="Pixel 8")
    b = login(env, device="Galaxy A15").json()
    sessions = env.client.get("/v1/me/sessions", headers=env.auth(a["token"])).json()["sessions"]
    assert {x["device"] for x in sessions} == {"Pixel 8", "Galaxy A15"}
    assert [x["current"] for x in sessions if x["device"] == "Pixel 8"] == [True]
    r = env.client.post("/v1/me/sessions/revoke-others", headers=env.auth(a["token"]))
    assert r.json() == {"ended": 1}
    assert me(env, b["token"]) == 401 and me(env, a["token"]) == 200


def test_ending_one_device_and_not_someone_elses(env) -> None:
    a = register(env, device="Pixel 8")
    b = login(env, device="Galaxy A15").json()
    other = register(env, email="other@example.com")
    sid_b = next(x["id"] for x in env.client.get("/v1/me/sessions", headers=env.auth(a["token"])).json()["sessions"]
                 if not x["current"])  # fmt: skip
    assert env.client.delete(f"/v1/me/sessions/{sid_b}", headers=env.auth(other["token"])).status_code == 404
    assert env.client.delete(f"/v1/me/sessions/{sid_b}", headers=env.auth(a["token"])).status_code == 200
    assert me(env, b["token"]) == 401


def test_expired_forged_and_old_style_tokens_are_rejected(env) -> None:
    body = register(env)
    key = env.services.settings.signing_key
    uid = body["user"]["id"]
    sid = env.client.get("/v1/me/sessions", headers=env.auth(body["token"])).json()["sessions"][0]["id"]
    assert me(env, issue_token(uid, key, ttl_s=-1, sid=sid)) == 401  # expired
    assert me(env, issue_token(uid, b"wrong-key", sid=sid)) == 401  # forged
    assert me(env, issue_token(uid, key, ttl_s=3600)) == 401  # old 30-day style: no session
    assert me(env, issue_token(uid, key, sid=sid)) == 200


def test_login_limits_per_account(env) -> None:
    register(env)
    for _ in range(5):
        assert login(env, password="wrong-password").status_code == 401
    r = login(env, password="wrong-password")
    assert r.status_code == 429  # 6th try within a minute


def test_ten_failures_lock_the_account_for_15_minutes(env) -> None:
    register(env)
    for i in range(10):
        env.services.limits.reset("login:siva@example.com")  # stay under the per-minute limit
        assert login(env, password="wrong-password").status_code == 401
    env.services.limits.reset("login:siva@example.com")
    r = login(env)  # even the right password
    assert r.status_code == 429 and "15 minutes" in r.json()["detail"]


def test_successful_login_clears_failures(env) -> None:
    register(env)
    for _ in range(4):
        login(env, password="wrong-password")
    assert login(env).status_code == 200
    assert env.services.limits.count("login-fail:siva@example.com", 900) == 0


PUBLIC = {("POST", "/v1/auth/register"), ("POST", "/v1/auth/login"), ("POST", "/v1/auth/demo"),
          ("POST", "/v1/auth/refresh"), ("GET", "/health"), ("GET", "/v1/languages"),
          ("GET", "/v1/users/check-username")}  # fmt: skip


def test_every_other_route_requires_sign_in(env) -> None:
    checked = 0
    for route in env.client.app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(("/v1", "/health")):
            continue
        path = route.path.replace("{", "").replace("}", "")  # fill path params with their own names
        for method in route.methods - {"HEAD", "OPTIONS"}:
            if (method, route.path) in PUBLIC:
                continue
            r = env.client.request(method, path, headers={"Authorization": "Bearer not-a-token"})
            assert r.status_code == 401, f"{method} {route.path} answered {r.status_code} without sign-in"
            checked += 1
    assert checked >= 30


def test_sockets_need_a_header_token_never_a_url_token(env) -> None:
    body = register(env)
    for path in [r.path for r in env.client.app.routes if isinstance(r, APIWebSocketRoute)]:
        url = path.replace("{call_id}", "nope")
        with pytest.raises(WebSocketDisconnect) as exc:
            with env.client.websocket_connect(f"{url}?token={body['token']}") as ws:
                ws.receive_text()
        assert exc.value.code == 4401
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(body["token"])) as ws:
        ws.send_json({"type": "ping", "t": 1})
        assert ws.receive_json() == {"type": "pong", "t": 1}


def test_old_chat_messages_and_voice_clips_are_deleted(env) -> None:
    ta, a = env.guest("A")
    tb, b = env.guest("B")
    conv = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]
    clip = env.services.chat_audio_dir / f"{'cd' * 16}.pcm"
    clip.write_bytes(b"\x00\x00" * 10)
    old = env.services.db.insert_message(conv["id"], a["id"], "A", "ta-IN", "old", audio_id="cd" * 16)
    new = env.services.db.insert_message(conv["id"], a["id"], "A", "ta-IN", "new")
    cutoff = time.time() - env.services.settings.chat_retention_days * 86400 - 10
    env.services.db._exec("UPDATE messages SET created_at = ?, expires_at = ? WHERE id = ?", (cutoff, cutoff, old["id"]))
    env.services.purge()
    ids = [m["id"] for m in env.services.db.get_messages(conv["id"])]
    assert ids == [new["id"]] and not clip.exists()
