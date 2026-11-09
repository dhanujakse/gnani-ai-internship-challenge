import pathlib
import tempfile
import pytest
from fastapi.testclient import TestClient

from sarvagyan_server.config import Settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app
from tests.fakes import FakeRecognizer, FakeSynth, FakeTranslator


@pytest.fixture
def test_client():
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, auth_secret="test-secret-value", gnani_api_key="gnani-test-key", data_dir=str(tmp), demo_mode=True)
    db = Database(tmp / "test.db")
    rec, tr, synth = FakeRecognizer(), FakeTranslator(), FakeSynth()
    svc = Services(settings, db=db, recognizer=rec, translator=tr, synthesizer_factory=lambda: synth, voicemail_pace_s=0)
    app = create_app(svc)
    with TestClient(app) as client:
        yield client, db


def test_username_search_a_and_b(test_client):
    client, db = test_client

    # Register user A
    r_a = client.post("/v1/auth/register", json={
        "email": "user_a@example.com",
        "password": "Password123!",
        "display_name": "Alice A",
        "username": "alice_hero",
    })
    assert r_a.status_code == 200, r_a.text
    token_a = r_a.json()["token"]
    user_a_id = r_a.json()["user"]["id"]

    # Register user B
    r_b = client.post("/v1/auth/register", json={
        "email": "user_b@example.com",
        "password": "Password123!",
        "display_name": "Bob B",
        "username": "bob_builder",
    })
    assert r_b.status_code == 200, r_b.text
    user_b_id = r_b.json()["user"]["id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. Search for B with exact username
    res1 = client.get("/v1/users/search?q=bob_builder", headers=headers_a)
    assert res1.status_code == 200
    users1 = res1.json()["users"]
    assert len(users1) >= 1
    found_b = next((u for u in users1 if u["id"] == user_b_id), None)
    assert found_b is not None
    assert found_b["username"] == "bob_builder"
    assert found_b["display_name"] == "Bob B"
    # Check return fields only contain expected keys: id, display_name, username, avatar
    assert set(found_b.keys()) == {"id", "display_name", "username", "avatar"}

    # 2. Search for B with leading '@'
    res2 = client.get("/v1/users/search?q=@bob_builder", headers=headers_a)
    assert res2.status_code == 200
    users2 = res2.json()["users"]
    assert any(u["id"] == user_b_id for u in users2)

    # 3. Search for B with case insensitivity and spaces
    res3 = client.get("/v1/users/search?q=  @BOB_builder  ", headers=headers_a)
    assert res3.status_code == 200
    assert any(u["id"] == user_b_id for u in res3.json()["users"])

    # 4. Search for B with prefix
    res4 = client.get("/v1/users/search?q=bob_", headers=headers_a)
    assert res4.status_code == 200
    assert any(u["id"] == user_b_id for u in res4.json()["users"])

    # 5. Searching for A from A must EXCLUDE current user A
    res5 = client.get("/v1/users/search?q=alice_hero", headers=headers_a)
    assert res5.status_code == 200
    assert all(u["id"] != user_a_id for u in res5.json()["users"])

    # 6. Searching for non-existent user returns empty list ("No user found")
    res6 = client.get("/v1/users/search?q=nonexistent_xyz_999", headers=headers_a)
    assert res6.status_code == 200
    assert res6.json()["users"] == []

    # 7. Searching for bare '@' returns empty list without error
    res7 = client.get("/v1/users/search?q=@", headers=headers_a)
    assert res7.status_code == 200
    assert res7.json()["users"] == []
