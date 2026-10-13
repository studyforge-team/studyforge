"""D8 done-when: a missed topic shows up as weak (what the next prep pack reads); real Postgres."""

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.agent.quiz import MCQItem, Quiz
from app.db import PgQuizStore, make_engine
from app.reminders import drain, schedule
from app.routers import checkins, dashboard, me, quizzes, uploads
from tests.unit.conftest import MemoryStorage

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
DEADLINE = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 20, tzinfo=UTC)
CHECKIN = DEADLINE + timedelta(hours=1, minutes=1)


def _item(topic: str) -> MCQItem:
    return MCQItem(type="mcq", topic=topic, stem="s", options=["a", "b", "c", "d"], correct_index=0,
                   misconceptions={1: "x", 2: "y", 3: "z"}, explanation="e")


async def _exercise(sent: list[str]) -> None:
    engine = make_engine()
    who = {"u": "A"}
    app = FastAPI()
    for r in (dashboard.router, checkins.router, quizzes.router, me.router):
        app.include_router(r)

    async def http() -> AsyncIterator[httpx.AsyncClient]:
        def ok(req: httpx.Request) -> httpx.Response:
            sent.append(str(req.url))
            return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(ok)) as c:
            yield c

    for mod in (dashboard, checkins, quizzes, me):
        if hasattr(mod, "current_user"):
            app.dependency_overrides[mod.current_user] = lambda: who["u"]
    app.dependency_overrides |= {checkins.get_engine: lambda: engine, me.get_engine: lambda: engine,
                                 me.get_http: http, checkins.now: lambda: CHECKIN}

    async def call(method: str, url: str, user: str = "A", **kw):  # type: ignore[no-untyped-def]
        who["u"] = user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, url, **kw)

    async def weak(user: str = "A") -> list[dict]:  # type: ignore[type-arg]
        return (await call("GET", "/api/v1/dashboard", user)).json()["weak_topics"]

    async def count(user: str) -> int:
        async with engine.connect() as c:
            return (await c.execute(text("select count(*) from app.topic_results where user_id=:u"),
                                    {"u": user})).scalar_one()

    # (a) the done-when: the missed topic is weak, the right one is not
    qid = await PgQuizStore(engine).save("A", Quiz(title="t", items=[_item("Heat exchangers"), _item("Distillation")]))
    body = {"answers": ["a", "a"], "score": 1, "correct": [False, True]}
    r = await call("POST", f"/api/v1/quizzes/{qid}/answers", json=body)
    assert r.status_code == 200 and r.json() == {"recorded": 2}
    assert await weak() == [{"topic": "Heat exchangers", "attempts": 1, "correct": 0}]

    # long free-text answers (subjective items) must not 422 and lose the quiz's results
    r = await call("POST", f"/api/v1/quizzes/{qid}/answers", json=body | {"answers": ["x" * 3000, "y"]})
    assert r.status_code == 200

    # (b) re-posting is idempotent
    assert (await call("POST", f"/api/v1/quizzes/{qid}/answers", json=body)).json() == {"recorded": 2}
    assert await weak() == [{"topic": "Heat exchangers", "attempts": 1, "correct": 0}]
    assert await count("A") == 2
    # wrong length of `correct` -> 422, nothing recorded
    bad = await call("POST", f"/api/v1/quizzes/{qid}/answers", json=body | {"correct": [True]})
    assert bad.status_code == 422 and await count("A") == 2

    # (c) another user's quiz (or an unknown id) is a 404 and changes nothing
    other = await call("POST", f"/api/v1/quizzes/{qid}/answers", "B", json=body | {"correct": [False, False]})
    assert other.status_code == 404
    assert (await call("POST", "/api/v1/quizzes/nope/answers", json=body)).status_code == 404
    assert await weak("B") == [] and await count("B") == 0
    assert await weak() == [{"topic": "Heat exchangers", "attempts": 1, "correct": 0}]

    # (d) check-ins count too, and spelling variants group together
    for title in ("Wrong", "Right"):
        await schedule(engine, "A", title, DEADLINE, NOW)
    await drain(engine, CHECKIN - timedelta(hours=2))
    got = {r["payload"]["title"]: r["id"] for r in await drain(engine, CHECKIN)}
    r = await call("POST", f"/api/v1/checkins/{got['Wrong']}", json={"correct": False, "topic": "Heat exchangers"})
    assert r.status_code == 200
    assert await weak() == [{"topic": "Heat exchangers", "attempts": 2, "correct": 0}]
    r = await call("POST", f"/api/v1/checkins/{got['Right']}", json={"correct": True, "topic": "heat  EXCHANGERS"})
    assert r.status_code == 200
    assert await weak() == [{"topic": "heat EXCHANGERS", "attempts": 3, "correct": 1}]  # 1/3 < 0.7, newest spelling
    # a check-in without a topic records nothing
    assert await count("A") == 4

    # (e) export carries the rows; DELETE /me removes them
    exported = (await call("GET", "/api/v1/me/export")).json()
    assert len(exported["topic_results"]) == 4 and {t["user_id"] for t in exported["topic_results"]} == {"A"}
    assert (await call("DELETE", "/api/v1/me")).status_code == 204
    assert sent == ["https://proj.supabase.co/auth/v1/admin/users/A"]
    assert await count("A") == 0
    await engine.dispose()


def test_topics_done_when(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    command.upgrade(CFG, "head")
    sent: list[str] = []
    try:
        asyncio.run(_exercise(sent))
    finally:
        command.downgrade(CFG, "base")
