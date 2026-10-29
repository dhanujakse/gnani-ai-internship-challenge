from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sarvagyan_server.config import Settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app
from tests.fakes import FakeRecognizer, FakeSynth, FakeTranslator


class Env:
    def __init__(self, client: TestClient, services: Services, rec: FakeRecognizer, tr: FakeTranslator,
                 synth: FakeSynth) -> None:  # fmt: skip
        self.client = client
        self.services = services
        self.rec = rec
        self.tr = tr
        self.synth = synth

    def guest(self, name: str) -> tuple[str, dict]:
        r = self.client.post("/v1/auth/demo", json={"display_name": name})
        assert r.status_code == 200, r.text
        body = r.json()
        return body["token"], body["user"]

    @staticmethod
    def auth(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def env(tmp_path) -> Iterator[Env]:
    settings = Settings(_env_file=None, auth_secret="test-secret-value", gnani_api_key="gnani-test-key",
                        data_dir=str(tmp_path), demo_mode=True)  # fmt: skip
    rec, tr, synth = FakeRecognizer(), FakeTranslator(), FakeSynth()
    services = Services(settings, db=Database(":memory:"), recognizer=rec, translator=tr,
                        synthesizer_factory=lambda: synth)  # fmt: skip
    with TestClient(create_app(services)) as client:
        yield Env(client, services, rec, tr, synth)
