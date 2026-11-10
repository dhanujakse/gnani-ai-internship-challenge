"""Discover from phone: you add your own number (as a hash) and people who have you in their contacts find you."""

import hashlib

from tests.test_direct_calls import people


def h(number: str) -> str:
    return hashlib.sha256(number.encode()).hexdigest()   # what the app sends: SHA-256 of the E.164 number


def test_adding_my_number_lets_friends_find_me(env) -> None:
    (ta, a), (tb, b) = people(env)
    r = env.client.patch("/v1/me", json={"phone_hash": h("+919876500001")}, headers=env.auth(ta))
    assert r.status_code == 200 and r.json()["phone_added"] is True
    found = env.client.post("/v1/contacts/match-phones", json={"phone_hashes": [h("+919876500001"), h("+919999999999")]},
                            headers=env.auth(tb)).json()["matches"]
    assert [(m["id"], m["phone_hash"]) for m in found] == [(a["id"], h("+919876500001"))]   # app can map it to the contact


def test_the_server_never_keeps_the_plain_hash(env) -> None:
    (ta, a), _ = people(env)
    env.client.patch("/v1/me", json={"phone_hash": h("+919876500002")}, headers=env.auth(ta))
    stored = env.services.db.get_user(a["id"])["phone_hash"]
    assert stored and stored != h("+919876500002")    # sealed with the server's secret


def test_bad_values_are_refused_and_empty_removes_the_number(env) -> None:
    (ta, a), (tb, b) = people(env)
    assert env.client.patch("/v1/me", json={"phone_hash": "12345"}, headers=env.auth(ta)).status_code == 422
    env.client.patch("/v1/me", json={"phone_hash": h("+919876500003")}, headers=env.auth(ta))
    r = env.client.patch("/v1/me", json={"phone_hash": ""}, headers=env.auth(ta))
    assert r.status_code == 200 and r.json()["phone_added"] is False
    found = env.client.post("/v1/contacts/match-phones", json={"phone_hashes": [h("+919876500003")]}, headers=env.auth(tb))
    assert found.json()["matches"] == []


def test_blocked_people_are_not_discovered(env) -> None:
    (ta, a), (tb, b) = people(env)
    env.client.patch("/v1/me", json={"phone_hash": h("+919876500004")}, headers=env.auth(ta))
    env.client.put(f"/v1/contacts/blocked/{b['id']}", headers=env.auth(ta))
    found = env.client.post("/v1/contacts/match-phones", json={"phone_hashes": [h("+919876500004")]}, headers=env.auth(tb))
    assert found.json()["matches"] == []
