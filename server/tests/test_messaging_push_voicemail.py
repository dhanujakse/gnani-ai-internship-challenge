"""Tests for Tasks 7, 8, and 9: gzip voice upload, chat_delivered, push notifications, and voicemail tag."""

import gzip
import time


def test_gzip_voice_upload_and_delivered_ws(env) -> None:
    ta, a = env.guest("Alice")
    tb, b = env.guest("Bob")
    env.client.patch("/v1/me", json={"language": "ta-IN"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(tb))
    cid = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]["id"]

    head = "SAY:ta-IN:வணக்கம்".encode("utf-8")
    pcm = head + b"\x00" * (32000 - len(head))
    gz = gzip.compress(pcm)
    assert len(gz) < len(pcm)

    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(ta)) as ws_a, \
            env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws_b:  # fmt: skip
        r = env.client.post(
            f"/v1/chat/conversations/{cid}/voice?language=ta-IN",
            content=gz,
            headers={**env.auth(ta), "Content-Encoding": "gzip"},
        )
        assert r.status_code == 200
        ev_b = ws_b.receive_json()
        assert ev_b["type"] == "message" and ev_b["message"]["audio_id"] == r.json()["message"]["audio_id"]
        # Sender receives chat_delivered immediately
        evs_a = [ws_a.receive_json() for _ in range(2)]
        assert any(e["type"] == "chat_delivered" and e["conversation_id"] == cid for e in evs_a)


def test_push_notifications_and_voicemail_missed_call(env) -> None:
    sent_pushes: list[tuple] = []

    async def fake_push(tokens, title, body, data):
        sent_pushes.append((list(tokens), title, body, dict(data)))

    env.services.push_sender = fake_push

    ta, a = env.guest("Alice")
    tb, b = env.guest("Bob")
    tc, c = env.guest("Charlie")
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(tb))
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(tc))

    # Register push tokens
    assert env.client.put("/v1/me/push-token", json={"token": "fcm_tok_alice_12345"}, headers=env.auth(ta)).status_code == 200
    assert env.client.put("/v1/me/push-token", json={"token": "fcm_tok_bob_12345"}, headers=env.auth(tb)).status_code == 200
    assert env.client.put("/v1/me/push-token", json={"token": "fcm_tok_charlie_12345"}, headers=env.auth(tc)).status_code == 200

    # 1:1 text message -> Bob gets push, Alice (sender) does NOT
    cid = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]["id"]
    env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": "Hello Bob"}, headers=env.auth(ta))
    assert len(sent_pushes) == 1
    assert sent_pushes[0][0] == ["fcm_tok_bob_12345"]
    assert sent_pushes[0][1] == "Alice"
    assert sent_pushes[0][2] == "Hello Bob"
    assert sent_pushes[0][3]["conversation_id"] == cid
    sent_pushes.clear()

    # If Bob has that chat focused over WS, Bob is NOT notified
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws_b:
        ws_b.send_json({"type": "chat_focus", "conversation_id": cid})
        time.sleep(0.03)
        env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": "While open"}, headers=env.auth(ta))
        assert sent_pushes == []

    # Group message -> sender + group name in title
    g = env.client.post("/v1/chat/groups", json={"name": "Family", "member_ids": [b["id"], c["id"]]}, headers=env.auth(ta)).json()["conversation"]
    env.client.post(f"/v1/chat/conversations/{g['id']}/messages", json={"text": "Hi group"}, headers=env.auth(ta))
    assert len(sent_pushes) == 2
    assert all("Alice · Family" == p[1] for p in sent_pushes)
    sent_pushes.clear()

    # Missed call + voicemail -> push body is "Voicemail" and Bob's missed-call history has has_voicemail=True
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
    call = env.client.post("/v1/calls/direct", json={"to": b["id"], "language": "en-IN"}, headers=env.auth(ta)).json()
    env.client.post(f"/v1/calls/{call['call_id']}/cancel", headers=env.auth(ta))

    pcm = b"SAY:en-IN:Call me back".ljust(32000, b"\x00")
    vm_resp = env.client.post(f"/v1/chat/conversations/{cid}/voice?language=en-IN&tag=voicemail", content=pcm, headers=env.auth(ta))
    assert vm_resp.status_code == 200 and vm_resp.json()["message"]["tag"] == "voicemail"
    assert len(sent_pushes) == 1 and sent_pushes[0][2] == "Voicemail"

    hist = env.client.get("/v1/calls/history", headers=env.auth(tb)).json()["calls"]
    assert hist[0]["status"] == "missed" and hist[0]["has_voicemail"] is True

    # Logout removes Bob's push token
    env.client.post("/v1/auth/logout", headers=env.auth(tb))
    sent_pushes.clear()
    env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": "After logout"}, headers=env.auth(ta))
    assert sent_pushes == []

