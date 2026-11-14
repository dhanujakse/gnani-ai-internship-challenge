def test_whatsapp_style_in_chat_voice_messages_two_accounts(env) -> None:
    ta, a = env.guest("Alice")
    tb, b = env.guest("Bob")
    tc, _ = env.guest("Outsider")
    env.client.patch("/v1/me", json={"language": "ta-IN"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(tb))

    conv = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]
    cid = conv["id"]

    # Minimum length validation (< MIN_BYTES)
    short_resp = env.client.post(f"/v1/chat/conversations/{cid}/voice?language=ta-IN", content=b"\x00" * 100, headers=env.auth(ta))
    assert short_resp.status_code == 422

    # Valid recording from Alice ("ta-IN") using FakeRecognizer frame format
    head = "SAY:ta-IN:நாளை சந்திக்கலாம்".encode("utf-8")
    pcm = head + b" " * (32000 - len(head))  # 1 second of 16 kHz PCM
    send_resp = env.client.post(f"/v1/chat/conversations/{cid}/voice?language=ta-IN", content=pcm, headers=env.auth(ta))
    assert send_resp.status_code == 200
    msg = send_resp.json()["message"]
    mid = msg["id"]
    audio_id = msg["audio_id"]
    assert audio_id and msg["duration_ms"] == 1000

    # Initially status is "sent" for Alice before Bob reads
    alice_msgs = env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(ta)).json()["messages"]
    assert alice_msgs[0]["status"] == "sent"

    # Bob opens thread -> receives transcript + English translation, and read ticks update to "read"
    import time as _time
    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(ta)) as ws_a:
        bob_msgs = env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(tb)).json()["messages"]
        assert len(bob_msgs) == 1
        read_ev = ws_a.receive_json()
        assert read_ev == {"type": "chat_read", "conversation_id": cid, "user_id": b["id"]}
        for _ in range(40):
            if bob_msgs[0]["original_text"] != "[Voice Message]":
                break
            _time.sleep(0.05)
            bob_msgs = env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(tb)).json()["messages"]
        bm = bob_msgs[0]
        assert bm["original_text"] == "நாளை சந்திக்கலாம்"
        assert bm["translated_text"] == "[en-IN] நாளை சந்திக்கலாம்"
        assert bm["is_translated"] is True
        assert bm["audio_url"] == f"/v1/chat/audio/{audio_id}"

    # Alice now sees "read" ticks
    alice_msgs_after = env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(ta)).json()["messages"]
    assert alice_msgs_after[0]["status"] == "read"

    # Bob plays original audio AND translated speech
    orig_audio = env.client.get(f"/v1/chat/audio/{audio_id}", headers=env.auth(tb))
    assert orig_audio.status_code == 200 and orig_audio.content == pcm

    trans_audio = env.client.get(f"/v1/chat/messages/{mid}/translated-audio", headers=env.auth(tb))
    assert trans_audio.status_code == 200 and len(trans_audio.content) > 0

    # Security: outsider C cannot play either audio endpoint
    assert env.client.get(f"/v1/chat/audio/{audio_id}", headers=env.auth(tc)).status_code == 404
    assert env.client.get(f"/v1/chat/messages/{mid}/translated-audio", headers=env.auth(tc)).status_code == 404


def test_translated_voice_reports_tts_failure_as_503(env) -> None:
    ta, _ = env.guest("Alice")
    tb, b = env.guest("Bob")
    env.client.patch("/v1/me", json={"language": "ta-IN"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(tb))
    cid = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]["id"]
    head = "SAY:ta-IN:நாளை சந்திக்கலாம்".encode("utf-8")
    sent = env.client.post(f"/v1/chat/conversations/{cid}/voice?language=ta-IN", content=head + b" " * (32000 - len(head)),
                           headers=env.auth(ta))  # fmt: skip
    mid = sent.json()["message"]["id"]
    import time as _time
    for _ in range(40):
        msgs = env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(tb)).json()["messages"]
        if msgs[0]["original_text"] != "[Voice Message]":
            break
        _time.sleep(0.05)
    env.synth.fail = True
    r = env.client.get(f"/v1/chat/messages/{mid}/translated-audio", headers=env.auth(tb))
    assert r.status_code == 503 and "original" in r.json()["detail"]


def test_diagnostics_checks_the_real_translator(env) -> None:
    t, _ = env.guest("Diag")
    out = env.client.get("/v1/diagnostics", headers=env.auth(t)).json()
    assert out["translation"]["ok"] is True  # FakeTranslator returns "[ta-IN] hello"


def test_translated_voice_reports_translation_failure_as_503(env) -> None:
    ta, _ = env.guest("Alice")
    tb, b = env.guest("Bob")
    env.client.patch("/v1/me", json={"language": "ta-IN"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(tb))
    cid = env.client.post("/v1/chat/direct", json={"user_id": b["id"]}, headers=env.auth(ta)).json()["conversation"]["id"]
    head = "SAY:ta-IN:நாளை சந்திக்கலாம்".encode("utf-8")
    mid = env.client.post(f"/v1/chat/conversations/{cid}/voice?language=ta-IN", content=head + b" " * (32000 - len(head)),
                          headers=env.auth(ta)).json()["message"]["id"]  # fmt: skip
    import time as _time
    for _ in range(40):  # wait for the transcript as the sender (same language: nothing to translate)
        msgs = env.client.get(f"/v1/chat/conversations/{cid}/messages", headers=env.auth(ta)).json()["messages"]
        if msgs[0]["original_text"] != "[Voice Message]":
            break
        _time.sleep(0.05)
    env.tr.fail = True
    r = env.client.get(f"/v1/chat/messages/{mid}/translated-audio", headers=env.auth(tb))
    assert r.status_code == 503 and "original" in r.json()["detail"]


def test_diagnostics_report_a_failing_translator(env) -> None:
    t, _ = env.guest("Diag2")
    env.tr.fail = True
    out = env.client.get("/v1/diagnostics", headers=env.auth(t)).json()
    assert out["translation"]["ok"] is False and out["translation"]["code"] == "timeout"
