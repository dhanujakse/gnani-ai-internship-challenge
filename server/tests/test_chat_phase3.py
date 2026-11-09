"""Phase 3: read receipts, delete for me / for everyone, chat history length, voice upload size limit."""

import time


def chat(env):
    ta, a = env.guest("A")
    tb, b = env.guest("B")
    conv = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]
    return ta, a, tb, b, conv["id"]


def send(env, token, cid, text="hello"):
    return env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": text}, headers=env.auth(token)).json()["message"]


def messages(env, token, cid):
    return env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(token)).json()["messages"]


def test_my_message_goes_sent_then_read(env) -> None:
    ta, a, tb, b, cid = chat(env)
    m = send(env, ta, cid)
    assert messages(env, ta, cid)[0]["status"] == "sent"
    assert messages(env, tb, cid)[0]["status"] is None  # not mine: no ticks
    assert messages(env, ta, cid)[0]["status"] == "read"  # B opened the chat


def test_delivered_when_it_reaches_their_phone(env) -> None:
    ta, a, tb, b, cid = chat(env)
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws:
        send(env, ta, cid)
        assert ws.receive_json()["type"] == "message"
    assert messages(env, ta, cid)[0]["status"] == "delivered"


def test_reader_gets_told_when_their_message_is_read(env) -> None:
    ta, a, tb, b, cid = chat(env)
    send(env, ta, cid)
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(ta)) as ws:
        messages(env, tb, cid)
        ev = ws.receive_json()
        assert ev == {"type": "chat_read", "conversation_id": cid, "user_id": b["id"]}


def test_read_receipts_off_works_both_ways(env) -> None:
    ta, a, tb, b, cid = chat(env)
    env.client.patch("/v1/me", json={"read_receipts": False}, headers=env.auth(tb))
    send(env, ta, cid)
    messages(env, tb, cid)
    assert messages(env, ta, cid)[0]["status"] == "delivered"  # B hides reads
    send(env, tb, cid, "reply")
    messages(env, ta, cid)
    assert messages(env, tb, cid)[-1]["status"] == "delivered"  # so B doesn't see A's either


def test_delete_for_everyone_removes_content_and_voice(env) -> None:
    ta, a, tb, b, cid = chat(env)
    m = send(env, ta, cid, "secret plan")
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ws:
        assert env.client.delete(f"/v1/chat/messages/{m['id']}", params={"scope": "everyone"},
                                 headers=env.auth(tb)).status_code == 403  # not the sender  # fmt: skip
        r = env.client.delete(f"/v1/chat/messages/{m['id']}", params={"scope": "everyone"}, headers=env.auth(ta))
        assert r.status_code == 200
        assert ws.receive_json() == {"type": "message_deleted", "conversation_id": cid, "message_id": m["id"]}
    for token in (ta, tb):
        got = messages(env, token, cid)[0]
        assert got["deleted"] is True and got["original_text"] == "" and "secret" not in str(got)
    assert "secret" not in str(env.services.db.get_message(m["id"]))


def test_delete_for_me_hides_only_for_me(env) -> None:
    ta, a, tb, b, cid = chat(env)
    m = send(env, ta, cid)
    assert env.client.delete(f"/v1/chat/messages/{m['id']}", headers=env.auth(tb)).status_code == 200
    assert messages(env, tb, cid) == []
    assert [x["id"] for x in messages(env, ta, cid)] == [m["id"]]


def test_outsiders_cannot_delete(env) -> None:
    ta, a, tb, b, cid = chat(env)
    tc, _ = env.guest("C")
    m = send(env, ta, cid)
    assert env.client.delete(f"/v1/chat/messages/{m['id']}", headers=env.auth(tc)).status_code == 404


def test_history_length_uses_the_shortest_setting_in_the_chat(env) -> None:
    ta, a, tb, b, cid = chat(env)
    assert env.client.patch("/v1/me", json={"chat_retention_days": 10}, headers=env.auth(tb)).status_code == 422
    env.client.patch("/v1/me", json={"chat_retention_days": 7}, headers=env.auth(tb))
    env.client.patch("/v1/me", json={"chat_retention_days": 365}, headers=env.auth(ta))
    assert env.client.get("/v1/me", headers=env.auth(ta)).json()["chat_retention_days"] == 365
    m = send(env, ta, cid)
    row = env.services.db.get_message(m["id"])
    assert abs(row["expires_at"] - row["created_at"] - 7 * 86400) < 5
    env.services.db._exec("UPDATE messages SET expires_at = ? WHERE id = ?", (time.time() - 1, m["id"]))
    env.services.purge()
    assert env.services.db.get_message(m["id"]) is None


def test_voice_upload_is_size_limited(env) -> None:
    ta, a, tb, b, cid = chat(env)
    too_big = b"\x00" * (env_max := 16000 * 2 * 61)
    r = env.client.post(f"/v1/chat/conversations/{cid}/voice", content=too_big, headers=env.auth(ta))
    assert r.status_code == 413 and env_max > 0
