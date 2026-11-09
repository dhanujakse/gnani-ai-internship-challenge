"""Spending the paid speech APIs carefully: silence gate, voice cache, budgets, idle close, usage report."""

import struct
import time

from sarvagyan_server.config import Settings
from sarvagyan_server.credits import Meter, SilenceGate, TtsCache, frame_rms
from tests.test_call_flow import say, two_party, until


def tone(amp: int, n: int = 512) -> bytes:
    return struct.pack(f"<{n}h", *([amp, -amp] * (n // 2)))


SILENT, QUIET, LOUD = bytes(1024), tone(60), tone(4000)


def test_gate_sends_only_speech_with_lead_in_and_tail() -> None:
    g = SilenceGate(preroll=4, hangover=3)
    sent = []
    for f in [QUIET] * 10:
        sent += g.push(f)
    assert sent == [] and g.skipped == 6           # 10 quiet frames: 4 held as lead-in, 6 never sent
    sent += g.push(LOUD)
    assert sent == [QUIET] * 4 + [LOUD]            # speech starts: lead-in first, so the first word isn't cut
    for f in [QUIET] * 3:
        sent += g.push(f)
    assert len(sent) == 8 and not g.open           # a short tail, then the gate closes again
    assert g.push(QUIET) == []


def test_zero_frames_from_the_app_echo_gate_never_open_it() -> None:
    g = SilenceGate()
    assert all(g.push(SILENT) == [] for _ in range(50)) and frame_rms(SILENT) == 0 and not g.open


def test_threshold_follows_background_noise() -> None:
    g = SilenceGate(min_rms=100, ratio=3)
    for _ in range(300):
        g.push(tone(200))                           # a steady hum (fan, traffic) about 10 s long
    assert g.threshold() > 200 and not g.open       # it stops counting as speech
    assert g.push(tone(4000)) and g.open            # a voice still opens the gate


def test_tts_cache_is_bounded_and_short_phrases_only() -> None:
    c = TtsCache(max_bytes=4000)
    k = TtsCache.key(" Hello  there ", "en-IN", "Kaveri", 1.0)
    assert k == TtsCache.key("hello there", "en-IN", "Kaveri", 1.0)
    assert c.cacheable("Okay") and not c.cacheable("x" * 200)
    c.put(k, [b"a" * 900]); assert c.get(k) == [b"a" * 900]
    for i in range(10):
        c.put(TtsCache.key(f"p{i}", "en-IN", "v", 1.0), [b"b" * 900])
    assert c.get(k) is None and c._size <= 4000      # oldest dropped, size stays within the limit


def test_meter_budgets() -> None:
    s = Settings(_env_file=None, daily_stt_minutes_per_user=1, daily_tts_chars_per_user=10, daily_server_tts_chars=0)
    m = Meter(s)
    assert m.stt_allowed("u") and m.tts_allowed("u", 10)
    m.add("u", "stt_s", 61); m.add("u", "tts_chars", 8)
    assert not m.stt_allowed("u") and not m.tts_allowed("u", 3) and m.stt_allowed("other")
    r = m.report()
    assert r["stt_minutes"] > 1 and list(r["users"]) == ["u"]


def test_repeated_phrase_is_voiced_once_then_served_from_cache(env) -> None:
    with two_party(env) as (_, (a, _ua), (b, _ub)):
        for _ in range(2):
            say(a, "ta-IN", "சரி")
            until(b, lambda m: m["type"] == "tts_end")
            until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
            time.sleep(1.6)                         # the same words within 1.5 s count as one (duplicate filter)
    assert [c[0] for c in env.synth.calls] == ["[en-IN] சரி"]   # paid once
    srv = env.services.meter.server()
    assert srv["tts_chars"] > 0 and srv["tts_cached_chars"] == srv["tts_chars"] and srv["stt_s"] > 0


def test_voice_budget_runs_out_into_subtitles_only(env) -> None:
    env.services.settings.daily_tts_chars_per_user = 5
    with two_party(env) as (_, (a, _), (b, _)):
        say(a, "ta-IN", "நீண்ட வாக்கியம் ஒன்று")
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] in ("skipped", "done") and m.get("translation"))
    assert done["stage"] == "skipped" and "subtitle" in done["error"] and env.synth.calls == []


def test_stream_closes_after_silence_and_reopens_quietly(env) -> None:
    env.services.settings.stt_idle_close_s = 0.3
    with two_party(env) as (_, (a, ua), (b, _)):
        first = env.rec.sessions[-1]
        for _ in range(60):                                    # wait for the idle close
            if any(s.closed for s in env.rec.sessions):
                break
            time.sleep(0.02)
        assert any(s.closed for s in env.rec.sessions)
        n = len(env.rec.sessions)
        say(a, "ta-IN", "மீண்டும்")                             # speech reopens a stream...
        done = until(b, lambda m: m["type"] == "utterance" and m["stage"] == "done")
        assert done["original"] == "மீண்டும்" and len(env.rec.sessions) > n
        assert first.closed


def test_usage_report_needs_the_admin_token(env) -> None:
    assert env.client.get("/v1/admin/usage").status_code == 401
    env.services.settings.admin_token = type(env.services.settings.admin_token)("s3cret-token")
    assert env.client.get("/v1/admin/usage", headers={"X-Admin-Token": "wrong"}).status_code == 401
    r = env.client.get("/v1/admin/usage", headers={"X-Admin-Token": "s3cret-token"})
    assert r.status_code == 200 and "silence_saved_pct" in r.json()
