"""End-to-end call flow over the real WebSocket endpoint with fake AI providers."""

import json
from contextlib import contextmanager

import pytest
from starlette.websockets import WebSocketDisconnect

from sarvagyan_server.providers.base import ProviderError


def recv(ws) -> dict | bytes:
    msg = ws.receive()
    if msg.get("bytes") is not None:
        return msg["bytes"]
    if msg["type"] == "websocket.close":
        raise WebSocketDisconnect(msg.get("code", 1000))
    return json.loads(msg["text"])


def until(ws, pred, limit: int = 80, collect: list | None = None) -> dict:
    """Read messages until pred(event) is true; binary frames go to `collect`."""
    for _ in range(limit):
        m = recv(ws)
        if isinstance(m, bytes):
            if collect is not None:
                collect.append(m)
            continue
        if pred(m):
            return m
    raise AssertionError("expected message never arrived")


def say(ws, lang: str, text: str) -> None:
    ws.send_bytes(f"SAY:{lang}:{text}".encode())


@contextmanager
def two_party(env, lang_a="ta-IN", lang_b="en-IN"):
    ta, ua = env.guest("Anbu")
    tb, ub = env.guest("Ben")
    call = env.client.post("/v1/calls", json={"language": lang_a}, headers=env.auth(ta)).json()
    env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": lang_b}, headers=env.auth(tb))
    url = f"/v1/calls/{call['call_id']}/ws"
    with env.client.websocket_connect(url, headers=env.auth(ta)) as a:
        a.send_json({"type": "hello", "language": lang_a, "voice": "Trisha"})
        until(a, lambda m: m["type"] == "joined")
        with env.client.websocket_connect(url, headers=env.auth(tb)) as b:
            b.send_json({"type": "hello", "language": lang_b, "voice": "Kaveri", "speed": 1.1})
            pa = until(a, lambda m: m["type"] == "peer_joined")
            pb = until(b, lambda m: m["type"] == "peer_joined")
            assert pa["initiator"] is True and pb["initiator"] is False  # first joiner makes the WebRTC offer
            until(a, lambda m: m.get("type") == "pipeline" and m["stt"] == "ready" and m["speaker_id"] == ua["id"])
            until(b, lambda m: m.get("type") == "pipeline" and m["stt"] == "ready" and m["speaker_id"] == ub["id"])
            yield call, (a, ua), (b, ub)


def test_websocket_requires_token_and_invitation(env) -> None:
    ta, _ = env.guest("A")
    tx, _ = env.guest("Stranger")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    url = f"/v1/calls/{call['call_id']}/ws"
    with pytest.raises(WebSocketDisconnect) as e:
        with env.client.websocket_connect(url) as ws:
            recv(ws)
    assert e.value.code == 4401
    with pytest.raises(WebSocketDisconnect) as e:
        with env.client.websocket_connect(url, headers=env.auth(tx)) as ws:
            recv(ws)
    assert e.value.code == 4404  # not invited: cannot listen in


def test_signalling_is_relayed_to_the_peer_only(env) -> None:
    with two_party(env) as (_, (a, ua), (b, _ub)):
        a.send_json({"type": "signal", "payload": {"sdp": "offer-sdp", "kind": "offer"}})
        got = until(b, lambda m: m["type"] == "signal")
        assert got["payload"] == {"sdp": "offer-sdp", "kind": "offer"} and got["from"] == ua["id"]


def test_tamil_to_english_reaches_only_the_listener(env) -> None:
    with two_party(env) as (_, (a, ua), (b, ub)):
        say(a, "ta-IN", "நாளை பள்ளிக்கு விடுமுறை")
        audio_b: list[bytes] = []
        start = until(b, lambda m: m["type"] == "tts_start", collect=audio_b)
        end = until(b, lambda m: m["type"] == "tts_end", collect=audio_b)
        assert start["id"] == end["id"] and end["ok"] is True and b"".join(audio_b)
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["speaker_id"] == ua["id"] and done["translation"] == "[en-IN] நாளை பள்ளிக்கு விடுமுறை"
        assert done["source_lang"] == "ta-IN" and done["target_lang"] == "en-IN"
        assert set(done["metrics"]) >= {"stt_ms", "translate_ms", "tts_first_ms", "server_total_ms"}
        # the speaker sees the same turn (for their subtitles) but never receives the synthetic audio
        mine: list[bytes] = []
        seen = until(a, lambda m: m["type"] == "utterance" and m["stage"] == "done", collect=mine)
        assert seen["id"] == done["id"] and mine == []
        # voice settings of the LISTENER are used
        assert env.synth.calls[-1] == ("[en-IN] நாளை பள்ளிக்கு விடுமுறை", "en-IN", "Kaveri", 1.1)


def test_stages_only_move_forward_and_are_ordered(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        say(a, "ta-IN", "ஒன்று")
        stages, revs = [], []
        for _ in range(40):
            m = recv(b)
            if isinstance(m, dict) and m["type"] == "utterance":
                stages.append(m["stage"])
                revs.append(m["rev"])
                if m["stage"] == "done":
                    break
        assert stages == ["recognized", "translating", "translated", "speaking", "done"]
        assert revs == sorted(revs)


def test_english_reply_is_translated_to_tamil(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, ub)):
        say(b, "en-IN", "I will call you back")
        audio: list[bytes] = []
        until(a, lambda m: m["type"] == "tts_end", collect=audio)
        done = until(a, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["speaker_id"] == ub["id"] and done["translation"] == "[ta-IN] I will call you back" and audio


def test_echo_of_translated_speech_is_not_retranslated(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, ub)):
        say(a, "ta-IN", "நாளை பள்ளிக்கு விடுமுறை")
        heard = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")["translation"]
        n_before = len(env.tr.calls)
        say(b, "en-IN", heard)  # B's mic picks up the English translation it just played
        say(b, "en-IN", "Okay thank you so much")  # then B really speaks
        got = until(a, lambda m: m["type"] == "utterance" and m["speaker_id"] == ub["id"] and m["stage"] == "recognized")
        assert got["original"] == "Okay thank you so much"
        assert [c[0] for c in env.tr.calls[n_before:]] == ["Okay thank you so much"]
        assert env.services.rooms[next(iter(env.services.rooms))].participants[ub["id"]].echo.blocked == 1


def test_translation_failure_keeps_call_and_can_retry(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        env.tr.fail = True
        say(a, "ta-IN", "வணக்கம்")
        failed = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "failed")
        assert failed["error"] == "Translation timed out." and failed["original"] == "வணக்கம்"
        env.tr.fail = False
        a.send_json({"type": "retry", "id": failed["id"]})
        done = until(b, lambda m: m["type"] == "utterance" and m["id"] == failed["id"] and m["stage"] == "done")
        assert done["translation"] == "[en-IN] வணக்கம்"


def test_voice_failure_still_delivers_subtitles(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        env.synth.fail = True
        say(a, "ta-IN", "சரி")
        err = until(b, lambda m: m["type"] == "error")
        assert err["scope"] == "tts"
        end = until(b, lambda m: m["type"] == "tts_end")
        assert end["ok"] is False
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["translation"] == "[en-IN] சரி" and "subtitle shown" in done["error"]


def test_listener_can_turn_off_translated_audio(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        b.send_json({"type": "settings", "translate_audio": False})
        until(a, lambda m: m["type"] == "participant")
        n = len(env.synth.calls)
        say(a, "ta-IN", "சரி")
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["translation"] == "[en-IN] சரி" and len(env.synth.calls) == n


def test_mute_stops_translation_input(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        a.send_json({"type": "settings", "muted": True})
        p = until(b, lambda m: m["type"] == "participant")
        assert p["participant"]["muted"] is True
        say(a, "ta-IN", "ரகசியம்")
        a.send_json({"type": "settings", "muted": False})
        until(b, lambda m: m["type"] == "participant" and m["participant"]["muted"] is False)
        say(a, "ta-IN", "இப்போது கேட்கும்")
        got = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "recognized")
        assert got["original"] == "இப்போது கேட்கும்"  # the muted phrase never reached recognition


def test_language_change_mid_call(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        a.send_json({"type": "settings", "language": "hi-IN"})
        until(b, lambda m: m["type"] == "participant" and m["participant"]["language"] == "hi-IN")
        assert ("update_language", "hi-IN") in env.rec.log
        a.send_json({"type": "settings", "language": "xx-XX"})
        err = until(a, lambda m: m["type"] == "error")
        assert err["code"] == "unsupported_language"


def test_same_language_needs_no_translation(env) -> None:
    with two_party(env, "en-IN", "en-IN") as (_, (a, _ua), (b, _ub)):
        n_tr, n_tts = len(env.tr.calls), len(env.synth.calls)
        say(a, "en-IN", "hello there")
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["translation"] == "hello there"
        assert (len(env.tr.calls), len(env.synth.calls)) == (n_tr, n_tts)


def test_auto_detect_uses_detected_language(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        a.send_json({"type": "settings", "auto_detect": True})
        until(b, lambda m: m["type"] == "participant" and m["participant"]["auto_detect"] is True)
        assert ("update_language", None) in env.rec.log  # indic-auto
        say(a, "hi-IN", "नमस्ते")
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["source_lang"] == "hi-IN" and env.tr.calls[-1] == ("नमस्ते", "hi-IN", "en-IN")


def test_stt_auth_failure_is_reported(env) -> None:
    env.rec.fail_with = ProviderError("gnani-stt", "auth", "Gnani rejected the API key (401). Check GNANI_API_KEY.")
    ta, _ = env.guest("A")
    tb, _ = env.guest("B")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=env.auth(tb))
    url = f"/v1/calls/{call['call_id']}/ws"
    with env.client.websocket_connect(url, headers=env.auth(ta)) as a, \
            env.client.websocket_connect(url, headers=env.auth(tb)) as b:  # fmt: skip
        a.send_json({"type": "hello", "language": "ta-IN"})
        b.send_json({"type": "hello", "language": "en-IN"})
        err = until(a, lambda m: m["type"] == "error" and m["scope"] == "stt")
        assert err["code"] == "auth" and err["retryable"] is False and "GNANI_API_KEY" in err["message"]
        assert "gnani-test-key" not in json.dumps(err)
        status = until(a, lambda m: m.get("type") == "pipeline" and m["stt"] == "error")
        assert "401" in status["message"]


def test_peer_reconnect_and_leave(env) -> None:
    ta, _ = env.guest("A")
    tb, ub = env.guest("B")
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=env.auth(tb))
    url = f"/v1/calls/{call['call_id']}/ws"
    with env.client.websocket_connect(url, headers=env.auth(ta)) as a:
        a.send_json({"type": "hello", "language": "ta-IN"})
        with env.client.websocket_connect(url, headers=env.auth(tb)) as b:
            b.send_json({"type": "hello", "language": "en-IN"})
            until(a, lambda m: m["type"] == "peer_joined")
        # B's socket dropped without "leave": A is told B is reconnecting, the seat is kept
        assert until(a, lambda m: m["type"] in ("peer_reconnecting", "peer_left"))["type"] == "peer_reconnecting"
        with env.client.websocket_connect(url, headers=env.auth(tb)) as b2:
            b2.send_json({"type": "hello", "language": "en-IN"})
            again = until(a, lambda m: m["type"] == "peer_joined")
            assert again["initiator"] is True  # A re-offers: WebRTC renegotiates after the drop
            b2.send_json({"type": "leave"})
            left = until(a, lambda m: m["type"] == "peer_left")
            assert left["reason"] == "left" and left["peer_id"] == ub["id"]
        a.send_json({"type": "leave"})
    hist = env.client.get("/v1/calls/history", headers=env.auth(ta)).json()["calls"][0]
    assert hist["status"] == "ended" and hist["duration_s"] is not None
