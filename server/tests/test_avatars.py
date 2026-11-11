import io
from PIL import Image


def _make_test_png(width: int = 800, height: int = 1000) -> bytes:
    im = Image.new("RGB", (width, height), color=(40, 120, 200))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_preset_and_uploaded_avatar_across_two_accounts_and_security(env) -> None:
    ta, ua = env.guest("Alice")
    tb, ub = env.guest("Bob")
    env.client.patch("/v1/me", json={"username": "alice_av"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"username": "bob_av"}, headers=env.auth(tb))
    env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb))
    env.client.post("/v1/contacts", json={"username": "alice_av"}, headers=env.auth(tb))

    # 1. Alice picks a preset avatar ("avatar-07")
    r = env.client.patch("/v1/me", json={"avatar": "avatar-07"}, headers=env.auth(ta))
    assert r.status_code == 200
    assert r.json()["avatar"] == "avatar-07"

    # Security: cannot spoof custom avatar id via PATCH /v1/me
    assert env.client.patch("/v1/me", json={"avatar": "custom:0123456789abcdef0123456789abcdef"}, headers=env.auth(tb)).status_code == 422

    # Bob sees Alice's preset avatar in search, contacts, chat list, incoming call, and live call
    search_b = env.client.get("/v1/users/search?q=alice_av", headers=env.auth(tb)).json()["users"]
    assert search_b[0]["avatar"] == "avatar-07"

    contacts_b = env.client.get("/v1/contacts", headers=env.auth(tb)).json()["contacts"]
    assert next(c for c in contacts_b if c["id"] == ua["id"])["avatar"] == "avatar-07"

    conv = env.client.post("/v1/chat/direct", json={"username": "alice_av"}, headers=env.auth(tb)).json()["conversation"]
    assert conv["peer"]["avatar"] == "avatar-07"

    with env.client.websocket_connect("/v1/chat/ws", headers=env.auth(tb)) as ring_b:
        call = env.client.post("/v1/calls/direct", json={"to": ub["id"], "language": "en-IN"}, headers=env.auth(ta)).json()
        inc = ring_b.receive_json()
        assert inc["type"] == "incoming_call" and inc["from"]["avatar"] == "avatar-07"
        env.client.post(f"/v1/calls/{call['call_id']}/answer", json={"language": "ta-IN"}, headers=env.auth(tb))
        url = f"/v1/calls/{call['call_id']}/ws"
        with env.client.websocket_connect(url, headers=env.auth(ta)) as wa, \
                env.client.websocket_connect(url, headers=env.auth(tb)) as wb:  # fmt: skip
            wa.send_json({"type": "hello"})
            wb.send_json({"type": "hello"})
            ev_b = None
            for _ in range(10):
                m = wb.receive_json()
                if m.get("type") == "joined":
                    ev_b = m
                    break
            assert ev_b is not None and ev_b["peer"]["avatar"] == "avatar-07"
            wa.send_json({"type": "leave"})
            wb.send_json({"type": "leave"})

    # 2. Alice uploads a custom photo -> cropped to 512x512 main + 128x128 thumb
    png_bytes = _make_test_png(800, 1000)
    up = env.client.post("/v1/me/avatar", content=png_bytes, headers=env.auth(ta))
    assert up.status_code == 200
    custom_id = up.json()["avatar"]
    assert custom_id and custom_id.startswith("custom:")
    fid = custom_id.removeprefix("custom:")

    # Fetch main (512x512) and thumb (128x128) (requires auth)
    assert env.client.get(f"/v1/avatars/{fid}").status_code == 401
    main_resp = env.client.get(f"/v1/avatars/{fid}", headers=env.auth(tb))
    thumb_resp = env.client.get(f"/v1/avatars/{fid}?thumb=1", headers=env.auth(tb))
    assert main_resp.status_code == 200 and thumb_resp.status_code == 200
    assert len(main_resp.content) <= 100 * 1024
    with Image.open(io.BytesIO(main_resp.content)) as im_main:
        assert im_main.size == (512, 512)
    with Image.open(io.BytesIO(thumb_resp.content)) as im_thumb:
        assert im_thumb.size == (128, 128)

    # Bob sees Alice's uploaded avatar in search & chat
    search_b2 = env.client.get("/v1/users/search?q=alice_av", headers=env.auth(tb)).json()["users"]
    assert search_b2[0]["avatar"] == custom_id

    # Security: path traversal & invalid uploads fail; unauthenticated upload rejected
    assert env.client.get("/v1/avatars/not_a_valid_id", headers=env.auth(tb)).status_code == 404
    assert env.client.post("/v1/me/avatar", content=png_bytes).status_code == 401
    assert env.client.post("/v1/me/avatar", content=b"not an image", headers=env.auth(ta)).status_code == 422
