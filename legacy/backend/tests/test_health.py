from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:  # context manager runs the lifespan
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_lifespan_creates_shared_http_client() -> None:
    with TestClient(app) as client:
        assert client.app.state.http is not None  # type: ignore[attr-defined]
