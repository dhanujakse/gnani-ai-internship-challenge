import asyncio
import json
import pathlib
import tempfile
import time
import pytest
from starlette.testclient import TestClient

from sarvagyan_server.config import Settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app
from tests.fakes import FakeRecognizer, FakeSynth, FakeTranslator


@pytest.fixture
def call_test_setup():
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, auth_secret="test-secret-value", gnani_api_key="gnani-test-key", data_dir=str(tmp), demo_mode=True)
    db = Database(tmp / "test.db")
    rec, tr, synth = FakeRecognizer(), FakeTranslator(), FakeSynth()
    svc = Services(settings, db=db, recognizer=rec, translator=tr, synthesizer_factory=lambda: synth, voicemail_pace_s=0)
    app = create_app(svc)
    return app, svc, db


def test_midcall_language_switch_and_notice(call_test_setup):
    app, svc, db = call_test_setup
    client = TestClient(app)

    # 1. Register Alice (Tamil) and Bob (English)
    res_a = client.post("/v1/auth/register", json={
        "email": "alice_call@example.com",
        "password": "Password123!",
        "display_name": "Alice",
        "username": "alice_call",
        "language": "ta-IN",
    })
    token_a = res_a.json()["token"]
    user_a = res_a.json()["user"]

    res_b = client.post("/v1/auth/register", json={
        "email": "bob_call@example.com",
        "password": "Password123!",
        "display_name": "Bob",
        "username": "bob_call",
        "language": "en-IN",
    })
    token_b = res_b.json()["token"]
    user_b = res_b.json()["user"]

    # 2. Alice creates a call
    res_call = client.post("/v1/calls", json={"language": "ta-IN"}, headers={"Authorization": f"Bearer {token_a}"})
    assert res_call.status_code == 200
    call_id = res_call.json()["call_id"]
    code = res_call.json()["invite_code"]

    # 3. Bob joins the call
    res_join = client.post("/v1/calls/join", json={"code": code, "language": "en-IN"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res_join.status_code == 200

    # 4. Connect WebSockets for both Alice and Bob
    with client.websocket_connect(f"/v1/calls/{call_id}/ws", headers={"Authorization": f"Bearer {token_a}"}) as ws_a, \
         client.websocket_connect(f"/v1/calls/{call_id}/ws", headers={"Authorization": f"Bearer {token_b}"}) as ws_b:

        # Alice and Bob send initial hello
        ws_a.send_json({"type": "hello", "language": "ta-IN"})
        ws_b.send_json({"type": "hello", "language": "en-IN"})

        # Drain initial ice_servers and participant events
        for _ in range(3):
            ws_a.receive_json()
            ws_b.receive_json()

        # Measure switch gap
        t0 = time.monotonic()

        # Alice switches language mid-call to English ("en-IN")
        ws_a.send_json({"type": "settings", "language": "en-IN"})

        # Bob must receive the switch notice: "Alice switched to English"
        received_notice = False
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 5.0:
            b_event = ws_b.receive_json()
            if b_event.get("type") == "notice" and b_event.get("code") == "language_switched":
                assert b_event.get("message") == "Alice switched to English"
                received_notice = True
                break

        switch_gap_ms = int((time.monotonic() - t0) * 1000)
        assert received_notice is True, "Bob did not receive Alice's switch notice!"

        # Alice receives updated participant info
        a_updated = False
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 5.0:
            a_event = ws_a.receive_json()
            if a_event.get("type") == "participant":
                p = a_event.get("participant", {})
                if p.get("user_id") == user_a["id"] and p.get("language") == "en-IN":
                    a_updated = True
                    break

        assert a_updated is True, "Alice did not receive updated language state!"
        print(f"Measured mid-call language switch gap: {switch_gap_ms} ms")
