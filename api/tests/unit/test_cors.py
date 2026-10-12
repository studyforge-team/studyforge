from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_allows_local_frontend_origin() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )


def test_preflight_allows_authorized_post_request() -> None:
    response = client.options(
        "/api/v1/dashboard",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )
    assert "POST" in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unapproved_origin_is_not_allowed() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "https://unapproved.example"},
    )

    assert "access-control-allow-origin" not in response.headers
