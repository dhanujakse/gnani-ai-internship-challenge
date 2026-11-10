"""Hanging up ends the call for the other person at once, even if the "leave" message never arrived."""

from tests.test_call_flow import two_party, until


def test_hang_up_close_code_ends_the_call_for_the_peer(env) -> None:
    with two_party(env) as (_, (a, ua), (b, _ub)):
        a.close(code=4000)  # the app's "I hung up" close, without sending {"type": "leave"}
        left = until(b, lambda m: m["type"] == "peer_left")
        assert left["peer_id"] == ua["id"] and left["reason"] == "left"   # not "connection_lost" after 30 s


def test_a_dropped_connection_still_gets_the_grace_period(env) -> None:
    with two_party(env) as (_, (a, ua), (b, _ub)):
        a.close(code=1006)  # network drop: the peer is told to wait, not that the call ended
        ev = until(b, lambda m: m["type"] in ("peer_reconnecting", "peer_left"))
        assert ev["type"] == "peer_reconnecting" and ev["peer_id"] == ua["id"]
