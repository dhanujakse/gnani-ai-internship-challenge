"""A call nobody answered shows up in both people's history: missed (or declined) for the person called."""

from tests.test_direct_calls import people


def ring(env, ta, b_id) -> str:
    r = env.client.post("/v1/calls/direct", json={"to": b_id, "language": "ta-IN"}, headers=env.auth(ta))
    assert r.status_code == 200, r.text
    return r.json()["call_id"]


def history(env, token) -> list[dict]:
    return env.client.get("/v1/calls/history", headers=env.auth(token)).json()["calls"]


def friends(env):
    (ta, a), (tb, b) = people(env)
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))   # b takes calls from a
    return ta, a, tb, b


def test_caller_cancelling_leaves_a_missed_call_for_the_callee(env) -> None:
    ta, a, tb, b = friends(env)
    cid = ring(env, ta, b["id"])
    assert env.client.post(f"/v1/calls/{cid}/cancel", headers=env.auth(ta)).status_code == 200
    mine = history(env, tb)
    assert [(h["call_id"], h["status"], h["direction"]) for h in mine] == [(cid, "missed", "incoming")]
    assert mine[0]["peer"]["id"] == a["id"]                                   # so they can call back
    theirs = history(env, ta)
    assert theirs[0]["status"] == "missed" and theirs[0]["direction"] == "outgoing" and theirs[0]["peer"]["id"] == b["id"]


def test_declined_call_is_marked_declined(env) -> None:
    ta, a, tb, b = friends(env)
    cid = ring(env, ta, b["id"])
    assert env.client.post(f"/v1/calls/{cid}/decline", headers=env.auth(tb)).status_code == 200
    assert history(env, tb)[0]["status"] == "declined" and history(env, ta)[0]["status"] == "declined"


def test_unanswered_call_times_out_as_missed(env) -> None:
    import time
    env.services.settings.ring_timeout_s = 0.3
    ta, a, tb, b = friends(env)
    cid = ring(env, ta, b["id"])
    for _ in range(40):
        if history(env, tb):
            break
        time.sleep(0.05)
    assert history(env, tb)[0]["call_id"] == cid and history(env, tb)[0]["status"] == "missed"
