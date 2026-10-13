from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, Self

import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.routers import me

URL = "https://proj.supabase.co"
calls: list[httpx.Request] = []


class Conn:
    def __init__(self) -> None:
        self.stmts: list[Any] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, stmt: Any) -> Self:
        self.stmts.append(stmt)
        return self

    def mappings(self) -> Self:
        return self

    def all(self) -> list[dict[str, Any]]:
        return [{"id": "x", "updated_at": datetime(2026, 1, 2, tzinfo=UTC)}]


class Engine:
    def __init__(self) -> None:
        self.conn = Conn()

    def connect(self) -> Conn:
        return self.conn

    begin = connect


@pytest.fixture
def setup(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Engine, dict[str, int]]]:
    monkeypatch.setenv("SUPABASE_URL", URL + "/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    calls.clear()
    eng = Engine()
    status = {"code": 200}

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(status["code"])

    async def http() -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides |= {me.current_user: lambda: "A", me.get_engine: lambda: eng, me.get_http: http}
    yield eng, status
    for k in (me.get_engine, me.get_http):
        app.dependency_overrides.pop(k, None)
    app.dependency_overrides[me.current_user] = auth.current_user


def test_export(setup: Any) -> None:
    r = TestClient(app).get("/api/v1/me/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="studyforge-export.json"'
    j = r.json()
    assert j["user_id"] == "A" and j["exported_at"]
    row = {"id": "x", "updated_at": "2026-01-02T00:00:00+00:00"}
    assert j["solves"] == j["quizzes"] == j["llm_calls"] == [row]


def test_delete_ok_and_auth_404_is_success(setup: Any) -> None:
    eng, status = setup
    c = TestClient(app)
    assert c.delete("/api/v1/me").status_code == 204
    assert len(eng.conn.stmts) == 3
    req = calls[0]
    assert req.method == "DELETE" and str(req.url) == f"{URL}/auth/v1/admin/users/A"
    assert req.headers["apikey"] == "svc" and req.headers["authorization"] == "Bearer svc"
    status["code"] = 404
    assert c.delete("/api/v1/me").status_code == 204


def test_auth_failure_is_502(setup: Any) -> None:
    setup[1]["code"] = 500
    r = TestClient(app).delete("/api/v1/me")
    assert r.status_code == 502 and "data deleted" in r.json()["detail"]


def test_missing_key_503_touches_nothing(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
    r = TestClient(app).delete("/api/v1/me")
    assert r.status_code == 503 and r.json() == {"detail": "not available"}
    assert setup[0].conn.stmts == [] and calls == []


def test_no_database_url_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides[me.current_user] = lambda: "A"
    try:
        assert TestClient(app).get("/api/v1/me/export").status_code == 503
    finally:
        app.dependency_overrides[me.current_user] = auth.current_user
