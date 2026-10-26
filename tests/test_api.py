import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from kuralcheck import api
from kuralcheck.audio.conditions import NoiseBank
from kuralcheck.fixlayer.lexicon import FormatRule, Lexicon, Rule
from kuralcheck.webapp import DailyCap
from tests.test_webapp import FakePrisma, FakeTimbre, speech_wav


class FakeState:
    def __init__(self, tmp_path: Path, key: str = "k", token: str = "") -> None:
        d = tmp_path / "noise"
        d.mkdir(exist_ok=True)
        sf.write(d / "n.wav", (0.1 * np.random.default_rng(0).standard_normal(32000)).astype(np.float32), 16000)
        self.key, self.token = key, token
        self.tts_model = "timbre-v2.5"
        self.noise = NoiseBank.load(d)
        self.bias = ("அவங்க",)
        self.lexicon = Lexicon([Rule("வந்தாங்கோ", "வந்தாங்க", "x")], [FormatRule(r"₹\s*(\d+)", r"\1 ரூபாய்")])
        self.cap = DailyCap(limit=100)
        self.prisma_fake = FakePrisma()

    def timbre(self):
        return FakeTimbre()

    def prisma(self, cached: bool = True):
        return self.prisma_fake


@pytest.fixture
def client_state(tmp_path):
    state = FakeState(tmp_path)
    api.app.dependency_overrides[api.get_state] = lambda: state
    yield TestClient(api.app), state
    api.app.dependency_overrides.clear()


def test_health(client_state) -> None:
    client, _ = client_state
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["gnani_key_configured"] is True
    assert body["fix_layer"] == {"bias_words": 1, "word_rules": 1, "format_rules": 1}
    assert body["noise_clips"] == ["n.wav"]


def test_score_and_fix_cost_nothing(client_state) -> None:
    client, state = client_state
    r = client.post("/v1/score", json={"reference": "பத்து ரூபாய்", "hypothesis": "10 ரூபாய்",
                                        "accepted_variants": ["பத்து=10"]}).json()  # fmt: skip
    assert r["cer"] == 0.0 and r["numbers"] == {"matched": 1, "in_reference": 1} and r["api_calls"] == 0
    assert client.post("/v1/score", json={"reference": "?? ...", "hypothesis": "x"}).status_code == 422
    f = client.post("/v1/fix", json={"text": "அவங்க வந்தாங்கோ ₹25"}).json()
    assert f["text"] == "அவங்க வந்தாங்க 25 ரூபாய்" and len(f["rules_applied"]) == 2
    assert state.prisma_fake.calls == []


def test_text_test_dedupes_and_reports(client_state) -> None:
    client, state = client_state
    r = client.post("/v1/test-text", json={"sentences": ["அவங்க வந்தாங்க", "அவங்க வந்தாங்க"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n"] == 1 and len(body["rows"]) == 2  # duplicate processed once
    assert body["stats"]["duplicates_skipped"] == 1
    assert len(state.prisma_fake.calls) == 4  # 2 conditions x (F0, F2)
    row = body["rows"][0]
    assert row["C4_F3"] == "அவங்க வந்தாங்க" and row["C4_F3_cer"] == 0.0
    assert row["audio"]["C1"].startswith("data:audio/wav;base64,")
    assert set(body["conditions"]) == {"C1", "C4"}


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"sentences": ["10 ரூபாய்"]}, 422),  # digits
        ({"sentences": ["hello"]}, 422),  # not Tamil
        ({"sentences": ["சரி"] * 11}, 422),  # too many
        ({"sentences": ["சரி"], "voice": "Nobody"}, 422),
    ],
)
def test_text_test_rejects_bad_input(client_state, payload, status) -> None:
    client, _ = client_state
    assert client.post("/v1/test-text", json=payload).status_code == status


def test_audio_test(client_state) -> None:
    client, _ = client_state
    r = client.post("/v1/test-audio", files={"file": ("rec.wav", speech_wav(2.0), "audio/wav")},
                    data={"reference": "அவங்க வந்தாங்க"})  # fmt: skip
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["phone_condition"] == "C3"
    assert body["C1_cer"] == 0.0 and body["C3_F3"] == "அவங்க வந்தாங்க"
    assert body["audio"]["C3"].startswith("data:audio/wav;base64,") and body["elapsed_ms"] >= 0


def test_token_auth(tmp_path) -> None:
    state = FakeState(tmp_path, token="s3cret")
    api.app.dependency_overrides[api.get_state] = lambda: state
    try:
        c = TestClient(api.app)
        assert c.post("/v1/fix", json={"text": "x"}).status_code == 401
        assert c.post("/v1/fix", json={"text": "x"}, headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert c.get("/health").status_code == 200  # health stays open
    finally:
        api.app.dependency_overrides.clear()


def test_no_key_is_503_and_cap_is_429(tmp_path) -> None:
    state = FakeState(tmp_path, key="")
    api.app.dependency_overrides[api.get_state] = lambda: state
    try:
        c = TestClient(api.app)
        assert c.post("/v1/test-text", json={"sentences": ["சரி"]}).status_code == 503
        state.key, state.cap = "k", DailyCap(limit=2)
        assert c.post("/v1/test-text", json={"sentences": ["சரி"]}).status_code == 429
    finally:
        api.app.dependency_overrides.clear()


def test_cors_allows_extension_origin(client_state) -> None:
    client, _ = client_state
    origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    r = client.options("/v1/fix", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == origin
    r = client.options("/v1/fix", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


def test_results_latest(client_state, tmp_path, monkeypatch) -> None:
    client, _ = client_state
    monkeypatch.setenv("KURALCHECK_RESULTS_DIR", str(tmp_path / "res"))
    assert client.get("/v1/results/latest").status_code == 404
    run = tmp_path / "res" / "2026-10-31_test"
    run.mkdir(parents=True)
    summary = {"run": {"split": "test", "created_at": "2026-10-31"},
               "overall": [{"model": "p", "source": "timbre", "condition": "C1", "setting": "F0", "n": 3,
                            "cer": {"value": 0.1, "low": 0.05, "high": 0.2, "n": 3}, "wer": None,
                            "number_accuracy": None, "failures": 0}]}  # fmt: skip
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    body = client.get("/v1/results/latest").json()
    assert body["run"] == "2026-10-31_test" and body["overall"][0]["n"] == 3
