import pathlib
import tempfile
import pytest
from starlette.testclient import TestClient

from sarvagyan_server.config import Settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app
from tests.fakes import FakeRecognizer, FakeSynth, FakeTranslator


@pytest.fixture
def lang_test_client():
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, auth_secret="test-secret-value", gnani_api_key="gnani-test-key", data_dir=str(tmp), demo_mode=True)
    db = Database(tmp / "test.db")
    rec, tr, synth = FakeRecognizer(), FakeTranslator(), FakeSynth()
    svc = Services(settings, db=db, recognizer=rec, translator=tr, synthesizer_factory=lambda: synth, voicemail_pace_s=0)
    app = create_app(svc)
    with TestClient(app) as client:
        yield client, db


def test_language_selection_signup_and_guest(lang_test_client):
    client, db = lang_test_client

    # 1. Register with Hindi language selection (not default Tamil)
    res_reg = client.post("/v1/auth/register", json={
        "email": "hindi_speaker@example.com",
        "password": "Password123!",
        "display_name": "Rohan Sharma",
        "username": "rohan_sharma",
        "language": "hi-IN",
    })
    assert res_reg.status_code == 200, res_reg.text
    reg_data = res_reg.json()
    assert reg_data["user"]["language"] == "hi-IN"

    # 2. Guest entry with Telugu selection (not default Tamil)
    res_guest = client.post("/v1/auth/demo", json={
        "display_name": "Telugu Guest",
        "username": "telugu_guest",
        "language": "te-IN",
    })
    assert res_guest.status_code == 200, res_guest.text
    guest_data = res_guest.json()
    assert guest_data["user"]["language"] == "te-IN"

    # 3. Invalid language code must fail with 422
    res_invalid = client.post("/v1/auth/register", json={
        "email": "alien@example.com",
        "password": "Password123!",
        "display_name": "Alien",
        "username": "alien_user",
        "language": "klingon-XX",
    })
    assert res_invalid.status_code == 422

    # 4. Verify editing language later in Settings via PATCH /v1/me
    token = reg_data["token"]
    headers = {"Authorization": f"Bearer {token}"}
    res_patch = client.patch("/v1/me", json={"language": "kn-IN"}, headers=headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["language"] == "kn-IN"

    # Verify updated profile persists in GET /v1/me
    res_me = client.get("/v1/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["language"] == "kn-IN"

