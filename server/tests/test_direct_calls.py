"""Phase 2: contacts, blocking, who-can-call-me, ringing direct calls (answer / decline / cancel / missed), TURN."""

import base64
import hashlib
import hmac
import time

import pytest
from starlette.websockets import WebSocketDisconnect


def people(env, n=2):
    out = []
    for i in range(n):
        token, user = env.guest(f"P{i}")
        env.client.patch("/v1/me", json={"username": f"person_{i}"}, headers=env.auth(token))
        out.append((token, user))
    return out


def phone(env, token):
    """The app's always-on socket (where rings arrive)."""
    return env.client.websocket_connect("/v1/chat/ws", headers=env.auth(token))


def next_event(ws, kind):
    for _ in range(20):
        ev = ws.receive_json()
        if ev.get("type") == kind:
            return ev
    raise AssertionError(f"no {kind} event")


def test_contacts_add_list_remove_by_username(env) -> None:
    (ta, a), (tb, b) = people(env)
    r = env.client.post("/v1/contacts", json={"username": "@person_1"}, headers=env.auth(ta))
    assert r.status_code == 200 and r.json()["contact"]["name"] == "P1" and "email" not in r.json()["contact"]
    assert [c["id"] for c in env.client.get("/v1/contacts", headers=env.auth(ta)).json()["contacts"]] == [b["id"]]
    assert env.client.post("/v1/contacts", json={"username": "nobody_here"}, headers=env.auth(ta)).status_code == 404
    assert env.client.post("/v1/contacts", json={"username": "person_0"}, headers=env.auth(ta)).status_code == 422
    env.client.delete(f"/v1/contacts/{b['id']}", headers=env.auth(ta))
    assert env.client.get("/v1/contacts", headers=env.auth(ta)).json()["contacts"] == []


def test_blocking_hides_and_stops_everything(env) -> None:
    (ta, a), (tb, b) = people(env)
    env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb))
    env.client.post("/v1/contacts", json={"user_id": b["id"]}, headers=env.auth(ta))
    assert env.client.put(f"/v1/contacts/blocked/{a['id']}", headers=env.auth(tb)).status_code == 200
    assert env.client.get("/v1/users/search", params={"q": "person"}, headers=env.auth(ta)).json()["users"] == []
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).status_code == 403
    assert env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).status_code == 404
    assert env.client.post("/v1/contacts", json={"username": "person_1"}, headers=env.auth(ta)).status_code == 404
    blocked = env.client.get("/v1/contacts/blocked", headers=env.auth(tb)).json()["contacts"]
    assert [x["id"] for x in blocked] == [a["id"]]
    env.client.delete(f"/v1/contacts/blocked/{a['id']}", headers=env.auth(tb))
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).status_code == 200


def test_only_contacts_can_call_by_default(env) -> None:
    (ta, a), (tb, b) = people(env)
    assert env.client.get("/v1/me", headers=env.auth(tb)).json()["allow_calls"] == "contacts"
    r = env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta))
    assert r.status_code == 403 and "contacts" in r.json()["detail"]
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))  # B adds A
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).status_code == 200
    assert env.client.patch("/v1/me", json={"allow_calls": "anyone"}, headers=env.auth(tb)).status_code == 422


def test_ring_then_answer(env) -> None:
    (ta, a), (tb, b) = people(env)
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
    with phone(env, tb) as ring_b, phone(env, ta) as ring_a:
        r = env.client.post("/v1/calls/direct", json={"to": b["id"], "language": "ta-IN"}, headers=env.auth(ta))
        call = r.json()
        assert call["ringing"] and call["reachable"] and call["peer_name"] == "P1"
        ev = next_event(ring_b, "incoming_call")
        assert ev["call_id"] == call["call_id"] and ev["from"]["name"] == "P0" and ev["from"]["language"] == "ta-IN"
        # the invite code of a ringing call cannot be used by anyone else
        tc, _ = env.guest("Stranger")
        j = env.client.post("/v1/calls/join", json={"code": call["invite_code"]}, headers=env.auth(tc))
        assert j.status_code == 404
        ans = env.client.post(f"/v1/calls/{call['call_id']}/answer", json={"language": "en-IN"}, headers=env.auth(tb))
        assert ans.status_code == 200 and ans.json()["peer_name"] == "P0"
        assert next_event(ring_a, "call_answered")["call_id"] == call["call_id"]
    # both can now open the call socket (the normal translated call)
    url = f"/v1/calls/{call['call_id']}/ws"
    with env.client.websocket_connect(url, headers=env.auth(ta)) as wa, \
            env.client.websocket_connect(url, headers=env.auth(tb)) as wb:  # fmt: skip
        for ws in (wa, wb):
            ws.send_json({"type": "hello"})
            assert next_event(ws, "joined")["call_id"] == call["call_id"]
        assert next_event(wa, "peer_joined")["peer"]["name"] == "P1"
        for ws in (wa, wb):
            ws.send_json({"type": "leave"})


def test_decline_tells_the_caller(env) -> None:
    (ta, a), (tb, b) = people(env)
    env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb))
    with phone(env, ta) as ring_a:
        call = env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).json()
        assert call["reachable"] is False  # B has no app socket open
        assert env.client.post(f"/v1/calls/{call['call_id']}/decline", headers=env.auth(ta)).status_code == 404
        assert env.client.post(f"/v1/calls/{call['call_id']}/decline", headers=env.auth(tb)).status_code == 200
        ev = next_event(ring_a, "call_declined")
        assert ev["peer_id"] == b["id"] and ev["peer_name"] == "P1"
    assert env.client.post(f"/v1/calls/{call['call_id']}/answer", json={}, headers=env.auth(tb)).status_code == 404


def test_caller_cancel_stops_the_ringing(env) -> None:
    (ta, a), (tb, b) = people(env)
    env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb))
    with phone(env, tb) as ring_b:
        call = env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).json()
        next_event(ring_b, "incoming_call")
        assert env.client.post(f"/v1/calls/{call['call_id']}/cancel", headers=env.auth(ta)).status_code == 200
        ev = next_event(ring_b, "call_cancelled")
        assert ev["reason"] == "cancelled" and ev["call_id"] == call["call_id"]


def test_no_answer_becomes_a_missed_call(env) -> None:
    (ta, a), (tb, b) = people(env)
    env.services.settings.ring_timeout_s = 0
    env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb))
    with phone(env, ta) as ring_a, phone(env, tb) as ring_b:
        call = env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).json()
        missed = next_event(ring_a, "call_missed")
        assert missed["call_id"] == call["call_id"] and missed["peer_name"] == "P1"
        assert next_event(ring_b, "call_cancelled")["reason"] == "missed"
    assert call["call_id"] not in env.services.calls


def test_other_people_cannot_answer_or_cancel(env) -> None:
    (ta, a), (tb, b), (tc, c) = people(env, 3)
    env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb))
    call = env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).json()
    assert env.client.post(f"/v1/calls/{call['call_id']}/answer", json={}, headers=env.auth(tc)).status_code == 404
    assert env.client.post(f"/v1/calls/{call['call_id']}/cancel", headers=env.auth(tb)).status_code == 404
    assert env.client.post(f"/v1/calls/{call['call_id']}/decline", headers=env.auth(tc)).status_code == 404


def test_chat_peer_profile_never_includes_email(env) -> None:
    ta, _ = env.guest("A")
    reg = env.client.post("/v1/auth/register", json={"email": "secret@example.com", "password": "longpassword",
                                                     "display_name": "B", "username": "bee_one"}).json()  # fmt: skip
    conv = env.client.post("/v1/chat/direct", json={"username": "bee_one"}, headers=env.auth(ta)).json()
    assert "secret@example.com" not in str(conv)


def test_turn_credentials_are_short_lived_and_signed(env) -> None:
    st = env.services.settings
    st.turn_urls = "turn:turn.example.com:3478"
    st.turn_secret = type(st.turn_credential)("shared-turn-secret")
    servers = st.ice_servers("user-1")
    turn = next(x for x in servers if x["urls"] == ["turn:turn.example.com:3478"])
    expiry, uid = turn["username"].split(":")
    assert uid == "user-1" and 0 < int(expiry) - time.time() <= 24 * 3600
    expected = base64.b64encode(hmac.new(b"shared-turn-secret", turn["username"].encode(), hashlib.sha1).digest()).decode()
    assert turn["credential"] == expected


def test_ringing_needs_sign_in_on_the_socket(env) -> None:
    with pytest.raises(WebSocketDisconnect):
        with env.client.websocket_connect("/v1/chat/ws") as ws:
            ws.receive_text()
