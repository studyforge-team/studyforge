from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_503_without_database(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert TestClient(app).get("/api/v1/dashboard").status_code == 503
