"""Phase 4: deleting an account removes everything the server holds about it."""


def delete(env, token, **body):
    return env.client.request("DELETE", "/v1/me", json=body, headers=env.auth(token))


def test_guest_deletes_account_and_all_their_data(env) -> None:
    ta, a = env.guest("A")
    tb, b = env.guest("B")
    env.client.patch("/v1/me", json={"username": "aaa_user"}, headers=env.auth(ta))
    cid = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]["id"]
    env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": "from A"}, headers=env.auth(ta))
    env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": "from B"}, headers=env.auth(tb))
    clip = env.services.chat_audio_dir / ("ef" * 16 + ".pcm")
    clip.write_bytes(b"\x00\x00")
    env.services.db.insert_message(cid, a["id"], "A", "ta-IN", "voice", audio_id="ef" * 16)
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
    env.services.db.insert_voicemail(a["id"], b["id"], "ta-IN", "en-IN", 1000)

    assert delete(env, ta, confirm="yes").status_code == 422
    assert delete(env, ta, confirm="DELETE").status_code == 200

    db = env.services.db
    assert db.get_user(a["id"]) is None and not clip.exists()
    assert env.client.get("/v1/me", headers=env.auth(ta)).status_code == 401  # session gone
    assert [m["original_text"] for m in db.get_messages(cid)] == ["from B"]  # B keeps their own messages
    assert env.client.get("/v1/contacts", headers=env.auth(tb)).json()["contacts"] == []
    assert db.voicemails(b["id"], sent=False) == []
    assert db.is_username_available("aaa_user")
    tables = ("users", "sessions", "contacts", "messages", "voicemails", "conversation_members", "call_participants")
    dump = "\n".join(str(list(r)) for t in tables for r in db._exec(f"SELECT * FROM {t}"))
    assert a["id"] not in dump


def test_email_account_needs_its_password(env) -> None:
    r = env.client.post("/v1/auth/register", json={"email": "x@example.com", "password": "longpassword",
                                                   "display_name": "X"}).json()  # fmt: skip
    token = r["token"]
    assert delete(env, token, confirm="DELETE").status_code == 403
    assert delete(env, token, confirm="DELETE", password="wrong-one").status_code == 403
    assert delete(env, token, confirm="DELETE", password="longpassword").status_code == 200
    login = env.client.post("/v1/auth/login", json={"email": "x@example.com", "password": "longpassword"})
    assert login.status_code == 401


def test_chat_with_no_members_left_is_removed(env) -> None:
    ta, a = env.guest("A")
    tb, b = env.guest("B")
    cid = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]["id"]
    env.client.post(f"/v1/chat/conversations/{cid}/messages", json={"text": "hi"}, headers=env.auth(tb))
    for t in (ta, tb):
        assert delete(env, t, confirm="DELETE").status_code == 200
    assert env.services.db.get_conversation(cid) is None and env.services.db.get_messages(cid) == []
