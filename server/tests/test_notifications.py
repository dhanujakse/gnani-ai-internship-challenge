"""Notifications: "added you as a contact" (with an opt-out), ringing a phone that opens mid-ring, and pushes only
when Firebase is configured."""

import json


def until(ws, pred, limit=30):
    for _ in range(limit):
        m = ws.receive_json()
        if pred(m):
            return m
    raise AssertionError("event not received")


def fake_pushes(env) -> list:
    sent: list = []

    async def push(tokens, title, body, data):
        sent.append((list(tokens), title, body, dict(data)))

    env.services.push_sender = push
    return sent


def test_contact_added_reaches_the_open_app(env) -> None:
    ta, a = env.guest("Anbu")
    tb, b = env.guest("Ben")
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws:
        env.client.post("/v1/contacts", json={"user_id": b["id"]}, headers=env.auth(ta))
        ev = until(ws, lambda m: m["type"] == "contact_added")
        assert ev["from"]["id"] == a["id"] and ev["from"]["name"] == "Anbu" and ev["is_contact"] is False
        # adding the same person again does not notify twice; adding back says they already have you
        env.client.post("/v1/contacts", json={"user_id": b["id"]}, headers=env.auth(ta))
        env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
        env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(ta))  # no new event either
    me_b = env.client.get("/v1/me", headers=env.auth(tb)).json()
    assert me_b["notify_contact_added"] is True


def test_contact_added_push_when_closed_and_opt_out(env) -> None:
    sent = fake_pushes(env)
    ta, a = env.guest("Anbu")
    tb, b = env.guest("Ben")
    tc, c = env.guest("Chitra")
    env.client.put("/v1/me/push-token", json={"token": "tok_ben_123456"}, headers=env.auth(tb))
    env.client.post("/v1/contacts", json={"user_id": b["id"]}, headers=env.auth(ta))
    assert [(p[0], p[1], p[3]) for p in sent] == [(["tok_ben_123456"], "Anbu", {"type": "contact_added", "user_id": a["id"]})]
    sent.clear()
    # Ben turns the notification off
    r = env.client.patch("/v1/me", json={"notify_contact_added": False}, headers=env.auth(tb))
    assert r.json()["notify_contact_added"] is False
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws:
        env.client.post("/v1/contacts", json={"user_id": b["id"]}, headers=env.auth(tc))
        ws.send_json({"type": "ping"})
        events = [ws.receive_json() for _ in range(1)]
        assert all(e["type"] != "contact_added" for e in events)
    assert sent == []


def test_phone_opened_from_the_call_push_still_rings(env) -> None:
    fake_pushes(env)
    ta, a = env.guest("Anbu")
    tb, b = env.guest("Ben")
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
    env.client.put("/v1/me/push-token", json={"token": "tok_ben_123456"}, headers=env.auth(tb))
    call = env.client.post("/v1/calls/direct", json={"to": b["id"], "language": "ta-IN"}, headers=env.auth(ta)).json()
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws:  # Ben opens the app
        ev = until(ws, lambda m: m["type"] == "incoming_call")
        assert ev["call_id"] == call["call_id"] and ev["from"]["id"] == a["id"] and ev["from"]["language"] == "ta-IN"
        assert 1 <= ev["expires_in"] <= env.services.settings.ring_timeout_s


def test_without_firebase_nothing_is_pushed_and_a_closed_app_is_unavailable(env, monkeypatch) -> None:
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    ta, a = env.guest("Anbu")
    tb, b = env.guest("Ben")
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
    env.client.put("/v1/me/push-token", json={"token": "tok_ben_123456"}, headers=env.auth(tb))
    assert env.services.push_enabled is False
    call = env.client.post("/v1/calls/direct", json={"to": b["id"], "language": "ta-IN"}, headers=env.auth(ta)).json()
    assert call["call_state"] == "unavailable"
    assert "tok_ben" not in json.dumps(call)
