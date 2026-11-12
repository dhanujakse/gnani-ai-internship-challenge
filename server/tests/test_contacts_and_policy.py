"""Tests for Priority 1: immediate contact add, username search suggestions, and Who Can Call Me policy."""

from tests.test_direct_calls import people


def test_add_contact_returns_contact_and_appears_immediately(env) -> None:
    (ta, a), (tb, b) = people(env)
    r = env.client.post("/v1/contacts", json={"user_id": b["id"]}, headers=env.auth(ta))
    assert r.status_code == 200
    c = r.json()["contact"]
    assert c["id"] == b["id"] and c["name"] == b["display_name"]
    listed = env.client.get("/v1/contacts", headers=env.auth(ta)).json()["contacts"]
    assert [x["id"] for x in listed] == [b["id"]]


def test_username_search_suggestions_trim_at_limit_10_and_fields(env) -> None:
    ta, a = env.guest("Me")
    env.client.patch("/v1/me", json={"username": "dhanu_me"}, headers=env.auth(ta))

    for i in range(12):
        ti, _ = env.guest(f"Dhanu Friend {i}")
        env.client.patch("/v1/me", json={"username": f"dhanu_user_{i:02d}"}, headers=env.auth(ti))

    # Backfill check: simulate a legacy user with NULL username_norm in DB
    tl, legacy = env.guest("LegacyUser")
    env.client.patch("/v1/me", json={"username": "dhanu_legacy"}, headers=env.auth(tl))
    env.services.db._exec("UPDATE users SET username_norm = NULL WHERE id = ?", (legacy["id"],))

    r = env.client.get("/v1/users/search", params={"q": "  @DhAnU  "}, headers=env.auth(ta))
    assert r.status_code == 200
    users = r.json()["users"]
    assert len(users) == 10
    assert all(u["id"] != a["id"] for u in users)
    for u in users:
        assert set(u.keys()) == {"id", "display_name", "username", "avatar"}

    # Exact legacy lookup after NULL username_norm still works
    r2 = env.client.get("/v1/users/search", params={"q": "@dhanu_legacy"}, headers=env.auth(ta))
    assert any(u["id"] == legacy["id"] for u in r2.json()["users"])


def test_who_can_call_me_three_accounts_even_after_prior_call(env) -> None:
    (ta, a), (tb, b), (tc, c) = people(env, 3)
    # B adds A as a contact; C is NOT in B's contacts
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))

    # Default is "contacts": A can call B, C cannot (403, does not ring)
    assert env.client.get("/v1/me", headers=env.auth(tb)).json()["allow_calls"] == "contacts"
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).status_code == 200
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(tc)).status_code == 403

    # B switches to "everyone": now C can call B
    assert env.client.patch("/v1/me", json={"allow_calls": "everyone"}, headers=env.auth(tb)).json()["allow_calls"] == "everyone"
    r_c = env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(tc))
    assert r_c.status_code == 200

    # B switches back to "contacts": C must be blocked again even though C called B earlier
    assert env.client.patch("/v1/me", json={"allow_calls": "contacts"}, headers=env.auth(tb)).json()["allow_calls"] == "contacts"
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(tc)).status_code == 403
    assert env.client.post("/v1/calls/direct", json={"to": b["id"]}, headers=env.auth(ta)).status_code == 200
