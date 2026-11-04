"""LIVE end-to-end test against the real Gnani (STT + TTS) and MyMemory APIs. Opt-in: uv run pytest -m live -s

Simulates a two-person call through the real server: participant A streams a real Tamil
recording (16 kHz PCM, 1,024-byte frames at real-time cadence, like the Android app) and
participant B (English) must receive the English translation and synthetic English audio.
Then B "replies" with English audio and A must hear Tamil. Uses a handful of API calls.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from sarvagyan_server.config import get_settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app

FIXTURES = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.live


def pcm_frames(path: Path) -> list[bytes]:
    x, sr = sf.read(path, dtype="float32")
    assert sr == 16000
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes() + bytes(32000)  # + 1 s silence ends the turn
    return [pcm[i:i + 1024].ljust(1024, b"\0") for i in range(0, len(pcm), 1024)]


def stream(ws, frames: list[bytes]) -> None:
    for f in frames:
        ws.send_bytes(f)
        time.sleep(0.032)


def collect(ws, speaker_id: str, timeout_s: float = 40.0) -> tuple[dict, int, dict]:
    """Read until the utterance from speaker_id is done; returns (final event, audio bytes, timings)."""
    t0 = time.monotonic()
    audio = 0
    marks: dict = {}
    while time.monotonic() - t0 < timeout_s:
        msg = ws.receive()
        if msg.get("bytes") is not None:
            audio += len(msg["bytes"])
            marks.setdefault("first_audio_s", round(time.monotonic() - t0, 2))
            continue
        m = json.loads(msg["text"])
        if m["type"] == "error":
            pytest.fail(f"provider error: {m}")
        if m["type"] == "utterance" and m["speaker_id"] == speaker_id:
            marks.setdefault(m["stage"] + "_s", round(time.monotonic() - t0, 2))
            if m["stage"] in ("done", "failed", "skipped"):
                return m, audio, marks
    pytest.fail("no translated utterance within timeout")


@pytest.fixture
def live_client(tmp_path):
    settings = get_settings()
    if not settings.gnani_api_key.get_secret_value():
        pytest.skip("GNANI_API_KEY not configured")
    with TestClient(create_app(Services(settings, db=Database(":memory:")))) as c:
        yield c


def test_live_two_way_tamil_english_call(live_client) -> None:
    c = live_client
    a = c.post("/v1/auth/demo", json={"display_name": "Live Tamil"}).json()
    b = c.post("/v1/auth/demo", json={"display_name": "Live English"}).json()
    ha, hb = {"Authorization": f"Bearer {a['token']}"}, {"Authorization": f"Bearer {b['token']}"}
    call = c.post("/v1/calls", json={"language": "ta-IN"}, headers=ha).json()
    c.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=hb)
    url = f"/v1/calls/{call['call_id']}/ws"
    with c.websocket_connect(url, headers=ha) as wa, c.websocket_connect(url, headers=hb) as wb:
        wa.send_json({"type": "hello", "language": "ta-IN", "voice": "Trisha"})
        wb.send_json({"type": "hello", "language": "en-IN", "voice": "Kaveri"})
        time.sleep(3)  # both STT sessions connect

        sender = threading.Thread(target=stream, args=(wa, pcm_frames(FIXTURES / "ta_holiday_asmita.wav")))
        t_start = time.monotonic()
        sender.start()
        done, audio, marks = collect(wb, a["user"]["id"])
        sender.join()
        print(f"\nTamil -> English: '{done['original']}' -> '{done['translation']}'")
        print(f"  stage times from first frame: {marks}; metrics {done['metrics']}; audio {audio} bytes")
        print(f"  wall clock {round(time.monotonic() - t_start, 2)} s for a {len(pcm_frames(FIXTURES / 'ta_holiday_asmita.wav')) * 0.032:.1f} s clip incl. 1 s silence")
        assert done["stage"] == "done" and done["translation"] and done["translation"] != done["original"]
        assert audio > 16000  # > 0.5 s of synthetic English speech reached B

        # English reply: synthesise test audio with the server's TTS path is not needed — reuse a fixture
        en = FIXTURES / "en_call_back_pranav.wav"
        if en.exists():
            sender = threading.Thread(target=stream, args=(wb, pcm_frames(en)))
            sender.start()
            done2, audio2, marks2 = collect(wa, b["user"]["id"])
            sender.join()
            print(f"English -> Tamil: '{done2['original']}' -> '{done2['translation']}' {marks2} {done2['metrics']}")
            assert done2["stage"] == "done" and done2["target_lang"] == "ta-IN" and audio2 > 16000
        wa.send_json({"type": "leave"})
        wb.send_json({"type": "leave"})


def test_live_tamil_voicemail_reaches_english_listener(live_client) -> None:
    """A real Tamil recording sent as voicemail: English text for the recipient, then English voice on play."""
    from sarvagyan_server.providers.mymemory import in_script

    c = live_client
    a = c.post("/v1/auth/demo", json={"display_name": "Live VM A"}).json()
    b = c.post("/v1/auth/demo", json={"display_name": "Live VM B"}).json()
    ha, hb = ({"Authorization": f"Bearer {s['token']}"} for s in (a, b))
    c.patch("/v1/me", json={"language": "en-IN"}, headers=hb)
    call = c.post("/v1/calls", json={"language": "ta-IN"}, headers=ha).json()
    c.post("/v1/calls/join", json={"code": call["invite_code"], "language": "en-IN"}, headers=hb)

    x, sr = sf.read(FIXTURES / "ta_meeting_trisha.wav", dtype="float32")
    assert sr == 16000
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    t0 = time.monotonic()
    r = c.post("/v1/voicemails", params={"to": b["user"]["id"], "language": "ta-IN"}, content=pcm, headers=ha)
    assert r.status_code == 202, r.text
    vid = r.json()["id"]
    item = None
    while time.monotonic() - t0 < 90:
        item = next(v for v in c.get("/v1/voicemails", headers=ha).json()["sent"] if v["id"] == vid)
        if item["status"] != "processing":
            break
        time.sleep(0.5)
    processed_s = round(time.monotonic() - t0, 1)
    assert item and item["status"] == "ready", item and item["error"]
    assert in_script(item["original"], "ta") and in_script(item["translation"], "en")
    inbox = c.get("/v1/voicemails", headers=hb).json()["inbox"]
    assert inbox and inbox[0]["id"] == vid
    t1 = time.monotonic()
    audio = c.get(f"/v1/voicemails/{vid}/audio", headers=hb)
    assert audio.status_code == 200 and len(audio.content) > 16000
    print(f"\nvoicemail: recording {len(pcm) / 32000:.1f}s, ready after {processed_s}s, "
          f"original {len(item['original'])} chars, translation {len(item['translation'])} chars, "
          f"voice {len(audio.content) / 32000:.1f}s in {time.monotonic() - t1:.1f}s")
