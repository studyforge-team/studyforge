"""app.wiring: 503 without config, one cached client, DbTools delegation."""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import auth, db, wiring
from app.main import app
from app.routers import solve


@pytest.fixture(autouse=True)
def fresh(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(wiring, "_cache", None)
    app.dependency_overrides[solve.current_user] = lambda: "u1"
    yield
    app.dependency_overrides[solve.current_user] = auth.current_user


def post() -> int:
    return TestClient(app).post("/api/v1/solve", json={"question": "q"}).status_code


def test_503_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TF_API_KEY", "k")
    assert post() == 503


def test_503_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    monkeypatch.delenv("TF_API_KEY", raising=False)
    assert post() == 503


def test_one_client_for_all_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    monkeypatch.setenv("TF_API_KEY", "k")
    a, b = wiring.get_deps(), wiring.get_deps()
    assert a is b and a.llm is b.llm
    assert type(a.llm.recorder).__name__ == "PgCostRecorder"  # type: ignore[attr-defined]


def test_deps_carry_chemlab_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    monkeypatch.setenv("TF_API_KEY", "k")
    assert "cstr" in (wiring.get_deps().templates or {})


def test_dbtools_delegate_and_never_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Any, ...]] = []

    async def fake(engine: Any, user: str, title: str, due: str) -> str:
        seen.append((engine, user, title, due))
        return "ok"

    monkeypatch.setattr(wiring, "schedule_reminder_tool", fake)

    class Boom:
        async def chat_json(self, *a: Any, **k: Any) -> Any:
            raise RuntimeError("model down")

    tools = wiring.DbTools("ENGINE", Boom())  # type: ignore[arg-type]
    assert asyncio.run(tools.schedule_reminder("u", "T", "D")) == "ok"
    assert seen == [("ENGINE", "u", "T", "D")]
    assert "Could not make a quiz" in asyncio.run(tools.make_quiz("u", "heat", 3))
