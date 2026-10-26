import pytest

from app.config import Settings


def test_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GNANI_API_KEY", "super-secret-key")
    s = Settings(_env_file=None)
    assert s.gnani_api_key.get_secret_value() == "super-secret-key"
    assert "super-secret-key" not in repr(s)


def test_allowed_origins_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.app, https://b.app")
    s = Settings(_env_file=None)
    assert s.allowed_origins_list == ["https://a.app", "https://b.app"]


def test_graph_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_GRAPH_VERSION", "v23.0")
    s = Settings(_env_file=None)
    assert s.wa_graph_base_url == "https://graph.facebook.com/v23.0"
