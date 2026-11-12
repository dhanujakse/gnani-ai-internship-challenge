import io
from PIL import Image


def test_preset_avatar_selection_all_14_and_validation(env) -> None:
    ta, a = env.guest("Alice")
    for i in range(1, 15):
        aid = f"avatar-{i:02d}"
        r = env.client.patch("/v1/me", json={"avatar": aid}, headers=env.auth(ta))
        assert r.status_code == 200, r.text
        assert r.json()["avatar"] == aid

    bad = env.client.patch("/v1/me", json={"avatar": "invalid-avatar"}, headers=env.auth(ta))
    assert bad.status_code == 422


def test_custom_avatar_upload_owner_only_and_square_crop(env) -> None:
    ta, a = env.guest("Alice")
    tb, b = env.guest("Bob")

    # Unauthenticated upload blocked
    unauth = env.client.post("/v1/me/avatar", content=b"123")
    assert unauth.status_code == 401

    # Non-square photo uploaded by Alice -> cropped to 512x512 WebP <= 100 KB, only updates Alice
    im = Image.new("RGB", (800, 1200), (40, 140, 90))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    up = env.client.post("/v1/me/avatar", content=buf.getvalue(), headers=env.auth(ta))
    assert up.status_code == 200, up.text
    av = up.json()["avatar"]
    assert av.startswith("custom:")
    fid = av.split(":", 1)[1]

    # Bob's avatar was NOT changed
    bob_me = env.client.get("/v1/me", headers=env.auth(tb)).json()
    assert bob_me.get("avatar") != av

    # Fetch main & thumb WebPs
    main_resp = env.client.get(f"/v1/avatars/{fid}", headers=env.auth(tb))
    assert main_resp.status_code == 200
    assert len(main_resp.content) <= 100 * 1024
    with Image.open(io.BytesIO(main_resp.content)) as out_im:
        assert out_im.size == (512, 512)

    thumb_resp = env.client.get(f"/v1/avatars/{fid}?thumb=true", headers=env.auth(tb))
    assert thumb_resp.status_code == 200
    with Image.open(io.BytesIO(thumb_resp.content)) as out_thumb:
        assert out_thumb.size == (128, 128)
