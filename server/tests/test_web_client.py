"""The browser (web app) path: CORS for the web origin, and WebSocket sign-in through a subprotocol.

Browsers can't send an Authorization header on a WebSocket, so the web app offers
["sarvagyan.v1", "auth.<token>"]; the server must accept that, answer with "sarvagyan.v1" only (never the token),
and keep refusing a token placed in the URL.
"""

import json

import pytest
from starlette.websockets import WebSocketDisconnect

WEB = "https://gnani-ai-internship-challenge.vercel.app"


def test_cors_allows_the_web_app_and_the_auth_header(env) -> None:
    r = env.client.options("/v1/auth/login", headers={"Origin": WEB, "Access-Control-Request-Method": "POST",
                                                       "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == WEB
    allowed = r.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed and "content-type" in allowed


def test_cors_refuses_other_websites(env) -> None:
    r = env.client.options("/v1/auth/login", headers={"Origin": "https://evil.example",
                                                       "Access-Control-Request-Method": "POST"})
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_call_socket_accepts_token_as_subprotocol(env) -> None:
    ta, _ = env.guest("Web A")
    tb, _ = env.guest("Web B")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=env.auth(tb))
    with env.client.websocket_connect(f"/v1/calls/{call['call_id']}/ws",
                                      subprotocols=["sarvagyan.v1", f"auth.{ta}"]) as ws:
        assert ws.accepted_subprotocol == "sarvagyan.v1"  # the token is never echoed back
        ws.send_text(json.dumps({"type": "hello", "language": "ta-IN"}))
        events = [json.loads(ws.receive_text()) for _ in range(2)]  # joined and ice_servers, in either order
        joined = next(e for e in events if e["type"] == "joined")
        assert joined["you"]["language"] == "ta-IN"


def test_chat_socket_accepts_token_as_subprotocol(env) -> None:
    t, _ = env.guest("Web chat")
    with env.client.websocket_connect("/v1/chat/ws", subprotocols=["sarvagyan.v1", f"auth.{t}"]) as ws:
        assert ws.accepted_subprotocol == "sarvagyan.v1"


def test_bad_subprotocol_token_and_url_token_are_refused(env) -> None:
    t, _ = env.guest("Web C")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(t)).json()
    with pytest.raises(WebSocketDisconnect) as bad:
        with env.client.websocket_connect(f"/v1/calls/{call['call_id']}/ws", subprotocols=["sarvagyan.v1", "auth.v1.nope.nope"]) as ws:
            ws.receive_text()
    assert bad.value.code == 4401
    with pytest.raises(WebSocketDisconnect) as in_url:
        with env.client.websocket_connect(f"/v1/calls/{call['call_id']}/ws?token={t}") as ws:
            ws.receive_text()
    assert in_url.value.code == 4401
