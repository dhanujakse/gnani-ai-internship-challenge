"""Translated voicemail: record in one language, the recipient reads and hears it in theirs."""

import time

import pytest

from sarvagyan_server import voicemail as vm
from sarvagyan_server.providers.base import ProviderError

TAMIL = "நாளைக்கு மீட்டிங் இருக்கு, கால் பண்ணுங்க"


def recording(lang: str, text: str, seconds: float = 1.0) -> bytes:
    """Fake microphone audio: the fake recogniser 'hears' the text in the first frame."""
    head = f"SAY:{lang}:{text}".encode()
    return head + b" " * (int(vm.SAMPLE_RATE * 2 * seconds) - len(head))


def called_each_other(env, lang_b: str = "en-IN"):
    ta, a = env.guest("Siva")
    tb, b = env.guest("Friend")
    env.client.patch("/v1/me", json={"language": "ta-IN"}, headers=env.auth(ta))   # guests default to English now
    env.client.patch("/v1/me", json={"language": lang_b}, headers=env.auth(tb))
    call = env.client.post("/v1/calls", json={"language": "ta-IN"}, headers=env.auth(ta)).json()
    env.client.post("/v1/calls/join", json={"code": call["invite_code"], "language": lang_b}, headers=env.auth(tb))
    return ta, a, tb, b


def send(env, token: str, to: str, body: bytes, language: str = "ta-IN", **extra):
    params = {"to": to, "language": language, **extra}
    return env.client.post("/v1/voicemails", params=params, content=body, headers=env.auth(token))


def wait_for(env, token: str, vid: str, box: str = "sent") -> dict:
    for _ in range(200):
        items = env.client.get("/v1/voicemails", headers=env.auth(token)).json()[box]
        item = next((v for v in items if v["id"] == vid), None)
        if item and item["status"] != "processing":
            return item
        time.sleep(0.01)
    raise AssertionError("voicemail never finished processing")


def test_tamil_voicemail_arrives_in_english(env) -> None:
    ta, a, tb, b = called_each_other(env)
    r = send(env, ta, b["id"], recording("ta-IN", TAMIL))
    assert r.status_code == 202, r.text
    vid = r.json()["id"]
    sent = wait_for(env, ta, vid)
    assert sent["status"] == "ready" and sent["contact"]["name"] == "Friend"
    box = env.client.get("/v1/voicemails", headers=env.auth(tb)).json()
    assert box["unread"] == 1
    item = box["inbox"][0]
    assert item["original"] == TAMIL and item["translation"] == f"[en-IN] {TAMIL}"
    assert item["source_lang"] == "ta-IN" and item["target_lang"] == "en-IN"
    assert item["contact"]["name"] == "Siva" and item["heard"] is False
    assert env.tr.calls[-1] == (TAMIL, "ta-IN", "en-IN")


def test_reply_goes_the_other_way(env) -> None:
    ta, a, tb, b = called_each_other(env)
    vid = send(env, tb, a["id"], recording("en-IN", "See you tomorrow"), language="en-IN").json()["id"]
    wait_for(env, tb, vid)
    item = env.client.get("/v1/voicemails", headers=env.auth(ta)).json()["inbox"][0]
    assert item["translation"] == "[ta-IN] See you tomorrow" and item["target_lang"] == "ta-IN"


def test_playback_is_generated_in_the_listeners_language_and_marks_heard(env) -> None:
    ta, a, tb, b = called_each_other(env)
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    wait_for(env, ta, vid)
    r = env.client.get(f"/v1/voicemails/{vid}/audio", headers=env.auth(tb))
    assert r.status_code == 200 and r.headers["x-sample-rate"] == "16000"
    assert r.content == b"\x01\x00" * 160 + b"\x02\x00" * 160
    text, lang, voice, _ = env.synth.calls[-1]
    assert text == f"[en-IN] {TAMIL}" and lang == "en-IN" and voice == "Kaveri"
    box = env.client.get("/v1/voicemails", headers=env.auth(tb)).json()
    assert box["unread"] == 0 and box["inbox"][0]["heard"] is True


def test_strangers_need_the_email_address(env) -> None:
    ta, a = env.guest("Siva")
    stranger = env.client.post("/v1/auth/register", json={"email": "Friend@Example.com", "password": "longpassword",
                                                           "display_name": "Friend"}).json()  # fmt: skip
    assert send(env, ta, stranger["user"]["id"], recording("ta-IN", TAMIL)).status_code == 404
    r = send(env, ta, "friend@example.com", recording("ta-IN", TAMIL))
    assert r.status_code == 202 and r.json()["contact"]["name"] == "Friend"
    assert send(env, ta, "nobody@example.com", recording("ta-IN", TAMIL)).status_code == 404
    assert send(env, ta, a["id"], recording("ta-IN", TAMIL)).status_code in (404, 422)


def test_only_sender_and_recipient_can_see_play_or_delete(env) -> None:
    ta, a, tb, b = called_each_other(env)
    tc, _ = env.guest("Other")
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    wait_for(env, ta, vid)
    assert env.client.get(f"/v1/voicemails/{vid}/audio", headers=env.auth(tc)).status_code == 404
    assert env.client.delete(f"/v1/voicemails/{vid}", headers=env.auth(tc)).status_code == 404
    assert env.client.get("/v1/voicemails", headers=env.auth(tc)).json() == {"inbox": [], "sent": [], "unread": 0}
    assert env.client.delete(f"/v1/voicemails/{vid}", headers=env.auth(tb)).status_code == 200
    assert env.client.get("/v1/voicemails", headers=env.auth(ta)).json()["sent"] == []


def test_length_limits(env) -> None:
    ta, a, tb, b = called_each_other(env)
    assert send(env, ta, b["id"], recording("ta-IN", "hi", seconds=0.2)).status_code == 422
    too_long = b"\x00" * (vm.MAX_BYTES + 2)
    assert send(env, ta, b["id"], too_long).status_code == 413
    assert send(env, ta, b["id"], recording("ta-IN", TAMIL), language="xx-XX").status_code == 422


def test_silence_fails_with_a_clear_message(env) -> None:
    ta, a, tb, b = called_each_other(env)
    vid = send(env, ta, b["id"], b"\x00" * vm.SAMPLE_RATE * 2).json()["id"]
    item = wait_for(env, ta, vid)
    assert item["status"] == "failed" and "No speech" in item["error"]
    assert env.client.get("/v1/voicemails", headers=env.auth(tb)).json()["inbox"] == []  # nothing delivered


def test_translation_failure_is_reported_to_the_sender(env) -> None:
    ta, a, tb, b = called_each_other(env)
    env.tr.fail = True
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    item = wait_for(env, ta, vid)
    assert item["status"] == "failed" and item["error"] == "Translation timed out."


def test_same_language_skips_translation(env) -> None:
    ta, a, tb, b = called_each_other(env, lang_b="ta-IN")
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    wait_for(env, ta, vid)
    item = env.client.get("/v1/voicemails", headers=env.auth(tb)).json()["inbox"][0]
    assert item["translation"] == TAMIL and env.tr.calls == []


def test_auto_detect_uses_the_detected_language(env) -> None:
    ta, a, tb, b = called_each_other(env, lang_b="ta-IN")
    vid = send(env, ta, b["id"], recording("en-IN", "Call me back"), auto_detect="true").json()["id"]
    wait_for(env, ta, vid)
    item = env.client.get("/v1/voicemails", headers=env.auth(tb)).json()["inbox"][0]
    assert item["source_lang"] == "en-IN" and item["translation"] == "[ta-IN] Call me back"
    assert env.rec.sessions[-1].language is None  # indic-auto


def test_voice_failure_returns_502_and_keeps_the_text(env) -> None:
    ta, a, tb, b = called_each_other(env)
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    wait_for(env, ta, vid)
    env.synth.fail = True
    r = env.client.get(f"/v1/voicemails/{vid}/audio", headers=env.auth(tb))
    assert r.status_code == 502 and "voice engine down" in r.json()["detail"]
    assert env.client.get("/v1/voicemails", headers=env.auth(tb)).json()["inbox"][0]["translation"]


def test_old_voicemails_are_deleted_after_a_week(env) -> None:
    ta, a, tb, b = called_each_other(env)
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    wait_for(env, ta, vid)
    env.services.db._exec("UPDATE voicemails SET created_at = ?", (time.time() - vm.RETENTION_S - 1,))
    assert env.client.get("/v1/voicemails", headers=env.auth(tb)).json()["inbox"] == []
    assert env.services.db.get_voicemail(vid) is None


def test_daily_cap(env) -> None:
    ta, a, tb, b = called_each_other(env)
    env.services.settings.daily_voicemail_cap = 1
    assert send(env, ta, b["id"], recording("ta-IN", TAMIL)).status_code == 202
    assert send(env, ta, b["id"], recording("ta-IN", TAMIL)).status_code == 429


@pytest.mark.asyncio
async def test_transcribe_joins_segments_and_sends_tail_silence() -> None:
    from tests.fakes import FakeRecognizer

    rec = FakeRecognizer()
    one_s = vm.FRAME_BYTES * 32 / (vm.SAMPLE_RATE * 2)  # whole frames, so each phrase starts a frame
    pcm = recording("ta-IN", "முதல்", one_s) + recording("ta-IN", "இரண்டு", one_s)
    text, detected = await vm.transcribe(rec, pcm, "ta-IN", pace_s=0, settle_s=0.01)
    assert text == "முதல் இரண்டு" and detected == "ta-IN"
    frames = len(pcm) // vm.FRAME_BYTES + int(vm.TAIL_SILENCE_S / vm.FRAME_S)
    assert rec.sessions[0].frames == frames and rec.sessions[0].closed


def test_provider_error_during_stt_marks_failed(env) -> None:
    ta, a, tb, b = called_each_other(env)
    env.rec.fail_with = ProviderError("gnani-stt", "auth", "Gnani rejected the API key (401).")
    vid = send(env, ta, b["id"], recording("ta-IN", TAMIL)).json()["id"]
    item = wait_for(env, ta, vid)
    assert item["status"] == "failed" and "401" in item["error"]
