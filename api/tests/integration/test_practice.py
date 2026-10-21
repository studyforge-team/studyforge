"""FO1 on a real Postgres: a practice result is stored, shows in quiz-attempts, is clamped and private."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db import make_engine
from app.routers import checkins, practice, progress

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))


async def _exercise() -> None:
    engine = make_engine()
    who = {"u": "A"}
    app = FastAPI()
    for r in (practice.router, progress.router):
        app.include_router(r)
    for mod in (practice, progress):
        app.dependency_overrides[mod.current_user] = lambda: who["u"]
    app.dependency_overrides[checkins.get_engine] = lambda: engine

    async def call(method: str, url: str, user: str = "A", **kw):  # type: ignore[no-untyped-def]
        who["u"] = user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, url, **kw)

    body = {"topic": "OA: ExxonMobil", "score": 11, "total": 15}
    assert (await call("POST", "/api/v1/practice-attempts", json=body)).json() == {"ok": True}
    got = (await call("GET", "/api/v1/quiz-attempts")).json()["topics"]
    assert [t["topic"] for t in got] == ["OA: ExxonMobil"]
    a = got[0]["attempts"][0]
    assert (a["score"], a["total"], a["marks_per_q"], a["quiz_id"]) == (11.0, 15.0, 1.0, "practice:OA: ExxonMobil")

    # a score above total is stored as total
    assert (await call("POST", "/api/v1/practice-attempts", json=body | {"score": 99})).status_code == 200
    scores = [x["score"] for x in (await call("GET", "/api/v1/quiz-attempts")).json()["topics"][0]["attempts"]]
    assert scores == [11.0, 15.0]

    # bad input stores nothing
    for bad in (body | {"total": 0}, body | {"marks_per_q": 3}, body | {"topic": ""}, body | {"x": 1}):
        assert (await call("POST", "/api/v1/practice-attempts", json=bad)).status_code == 422
    assert len((await call("GET", "/api/v1/quiz-attempts")).json()["topics"][0]["attempts"]) == 2

    # another user does not see it
    assert (await call("GET", "/api/v1/quiz-attempts", "B")).json() == {"topics": []}
    await engine.dispose()


def test_practice_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
