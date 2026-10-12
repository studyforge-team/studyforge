from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OK = "https://studyforge-ten-alpha.vercel.app"


def _preflight(origin: str):
    return client.options(
        "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )


def test_allowed_origin_gets_header():
    assert _preflight(OK).headers["access-control-allow-origin"] == OK


def test_other_origin_gets_no_header():
    assert "access-control-allow-origin" not in _preflight("https://evil.example").headers
