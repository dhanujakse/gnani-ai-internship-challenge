import pytest

from kuralcheck.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.tts_model == "timbre-v2.5"
    assert s.language_code == "ta-IN"
    assert s.cache_path.endswith(".sqlite")


def test_key_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GNANI_API_KEY", "secret-123")
    s = Settings(_env_file=None)
    assert s.gnani_api_key.get_secret_value() == "secret-123"
    assert "secret-123" not in repr(s)
