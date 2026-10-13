from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_keepalive_without_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = client.get("/keepalive")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "off"}
    assert client.head("/keepalive").status_code == 200
