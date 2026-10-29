import pytest

from sarvagyan_server.security import (
    hash_password,
    issue_token,
    normalise_invite_code,
    verify_password,
    verify_token,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert "correct" not in h


def test_tokens_sign_and_expire() -> None:
    t = issue_token("u1", b"k", ttl_s=60, now=1000)
    assert verify_token(t, b"k", now=1010) == "u1"
    assert verify_token(t, b"other", now=1010) is None  # forged
    assert verify_token(t, b"k", now=2000) is None  # expired
    assert verify_token(t[:-2] + "xx", b"k", now=1010) is None


def test_register_login_flow(env) -> None:
    c = env.client
    r = c.post("/v1/auth/register", json={"email": "Asha@Example.com", "password": "s3cretpass", "display_name": "Asha"})
    assert r.status_code == 200
    assert c.post("/v1/auth/register", json={"email": "asha@example.com", "password": "s3cretpass",
                                             "display_name": "A"}).status_code == 409  # fmt: skip
    assert c.post("/v1/auth/login", json={"email": "asha@example.com", "password": "nope"}).status_code == 401
    ok = c.post("/v1/auth/login", json={"email": "asha@example.com", "password": "s3cretpass"})
    assert ok.status_code == 200
    me = c.get("/v1/me", headers=env.auth(ok.json()["token"])).json()
    assert me["display_name"] == "Asha" and me["is_demo"] is False


def test_short_password_rejected(env) -> None:
    r = env.client.post("/v1/auth/register", json={"email": "b@x.io", "password": "short", "display_name": "B"})
    assert r.status_code == 422


def test_demo_mode_and_bad_token(env) -> None:
    token, user = env.guest("Guest Tamil")
    assert user["is_demo"] is True
    assert env.client.get("/v1/me", headers=env.auth("v1.bad.token")).status_code == 401
    env.services.settings.demo_mode = False
    assert env.client.post("/v1/auth/demo", json={"display_name": "x"}).status_code == 403


def test_languages_catalog_tamil_english_first(env) -> None:
    body = env.client.get("/v1/languages").json()
    codes = [l["code"] for l in body["languages"]]
    assert codes[:2] == ["ta-IN", "en-IN"] and len(codes) == 10
    assert body["languages"][0]["voices"][0] == "Trisha"


def test_update_language_validation(env) -> None:
    token, _ = env.guest("G")
    assert env.client.patch("/v1/me", json={"language": "xx-YY"}, headers=env.auth(token)).status_code == 422
    assert env.client.patch("/v1/me", json={"language": "en-IN"}, headers=env.auth(token)).json()["language"] == "en-IN"


def test_create_and_join_call(env) -> None:
    ta, _ = env.guest("A")
    tb, _ = env.guest("B")
    tc, _ = env.guest("C")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    assert len(call["invite_code"]) == 6 and call["app_link"].endswith(call["invite_code"])
    messy = call["invite_code"][:3].lower() + "-" + call["invite_code"][3:]
    j = env.client.post("/v1/calls/join", json={"code": messy, "language": "en-IN"}, headers=env.auth(tb))
    assert j.status_code == 200 and j.json()["call_id"] == call["call_id"]
    full = env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=env.auth(tc))
    assert full.status_code == 409


def test_invalid_code_and_language(env) -> None:
    t, _ = env.guest("A")
    assert env.client.post("/v1/calls/join", json={"code": "ZZZZZZ"}, headers=env.auth(t)).status_code == 404
    assert env.client.post("/v1/calls", json={"language": "fr-FR"}, headers=env.auth(t)).status_code == 422
    assert env.client.post("/v1/calls", json={"language": "ta-IN"}).status_code == 401


def test_invite_code_normalisation() -> None:
    assert normalise_invite_code(" ab-c 2d3 ") == "ABC2D3"


def test_ice_servers_need_auth_and_hide_nothing_secret(env) -> None:
    t, _ = env.guest("A")
    assert env.client.get("/v1/ice-servers").status_code == 401
    body = env.client.get("/v1/ice-servers", headers=env.auth(t)).json()
    assert body["ice_servers"][0]["urls"][0].startswith("stun:")


@pytest.mark.parametrize("path", ["/health", "/v1/languages"])
def test_public_endpoints_never_contain_secrets(env, path) -> None:
    text = env.client.get(path).text
    assert "gnani-test-key" not in text and "test-secret-value" not in text


def test_favourites_only_for_people_you_called(env) -> None:
    ta, a = env.guest("A")
    tb, b = env.guest("B")
    tc, c = env.guest("C")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=env.auth(tb))
    assert env.client.put(f"/v1/contacts/favourites/{c['id']}", headers=env.auth(ta)).status_code == 404
    assert env.client.put(f"/v1/contacts/favourites/{b['id']}", headers=env.auth(ta)).status_code == 200
    favs = env.client.get("/v1/contacts/favourites", headers=env.auth(ta)).json()["contacts"]
    assert [f["name"] for f in favs] == ["B"] and favs[0]["is_demo"] is True
    hist = env.client.get("/v1/calls/history", headers=env.auth(ta)).json()["calls"]
    assert hist[0]["peer"]["name"] == "B" and hist[0]["peer"]["favourite"] is True
