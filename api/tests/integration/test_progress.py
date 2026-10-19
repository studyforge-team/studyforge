"""T4 on a real Postgres: an attempt is stored on save, listed per topic, private, exported and deleted."""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.agent.quiz import MCQItem, Quiz
from app.db import make_engine, quizzes
from app.routers import checkins, me, progress, uploads
from app.routers import quizzes as quizzes_router
from tests.unit.conftest import MemoryStorage

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))


def _item(topic: str = "x") -> MCQItem:
    return MCQItem(type="mcq", topic=topic, stem="s", options=["a", "b", "c", "d"], correct_index=0,
                   misconceptions={1: "x", 2: "y", 3: "z"}, explanation="e")


async def _exercise() -> None:
    engine = make_engine()
    who = {"u": "A"}
    app = FastAPI()
    for r in (quizzes_router.router, progress.router, me.router):
        app.include_router(r)

    async def http() -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as c:
            yield c

    files = MemoryStorage()
    for mod in (quizzes_router, progress, me):
        app.dependency_overrides[mod.current_user] = lambda: who["u"]
    app.dependency_overrides |= {checkins.get_engine: lambda: engine, me.get_engine: lambda: engine,
                                 me.get_http: http, uploads.get_storage_opt: lambda: files}

    async def call(method: str, url: str, user: str = "A", **kw):  # type: ignore[no-untyped-def]
        who["u"] = user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, url, **kw)

    async def put(user: str, quiz: dict, qid: str) -> None:  # type: ignore[type-arg]
        async with engine.begin() as c:
            await c.execute(quizzes.insert().values(id=qid, user_id=user, quiz=quiz))

    titled = Quiz(title="Titled quiz", items=[_item(), _item(), _item()]).model_dump(mode="json")
    await put("A", titled, "q-title")
    await put("A", titled | {"topic": "Reactors", "marks_per_q": 2}, "q-topic")
    await put("A", titled | {"topic": "Reactors"}, "q-topic2")
    await put("B", titled | {"topic": "Reactors"}, "q-b")

    async def save(qid: str, score: float, correct: list, user: str = "A"):  # type: ignore[no-untyped-def,type-arg]
        return await call("POST", f"/api/v1/quizzes/{qid}/answers", user,
                          json={"answers": ["a"] * 3, "score": score, "correct": correct})

    # (a) inserted on save; response unchanged; topic falls back to title; total = non-null count
    assert (await save("q-title", 1, [True, False, None])).json() == {"recorded": 2}
    assert (await save("q-topic", 4, [True, True, True])).json() == {"recorded": 3}
    assert (await save("q-topic2", 2, [True, False, False])).status_code == 200
    async with engine.connect() as c:
        rows = (await c.execute(text("select topic, score, total, marks_per_q from app.quiz_attempts "
                                     "where user_id='A' order by id"))).all()
    assert rows == [("Titled quiz", 1.0, 2.0, 1.0), ("Reactors", 4.0, 3.0, 2.0), ("Reactors", 2.0, 3.0, 1.0)]
    # a 404 / 422 save stores nothing
    assert (await save("q-b", 1, [True, True, True])).status_code == 404
    assert (await save("q-topic", 1, [True])).status_code == 422
    async with engine.connect() as c:
        assert (await c.execute(text("select count(*) from app.quiz_attempts"))).scalar_one() == 3

    # (b) GET groups per topic, oldest first; topics by latest attempt
    got = (await call("GET", "/api/v1/quiz-attempts")).json()["topics"]
    assert [t["topic"] for t in got] == ["Reactors", "Titled quiz"]
    assert [a["quiz_id"] for a in got[0]["attempts"]] == ["q-topic", "q-topic2"]
    assert got[0]["attempts"][0] | {"created_at": None} == {
        "quiz_id": "q-topic", "score": 4.0, "total": 3.0, "marks_per_q": 2.0, "created_at": None}
    assert got[1]["attempts"][0]["quiz_id"] == "q-title"

    # (c) owner isolation
    assert (await call("GET", "/api/v1/quiz-attempts", "B")).json() == {"topics": []}
    assert (await save("q-b", 3, [True, True, True], "B")).status_code == 200
    only_b = (await call("GET", "/api/v1/quiz-attempts", "B")).json()["topics"]
    assert [a["quiz_id"] for a in only_b[0]["attempts"]] == ["q-b"]
    assert sum(len(t["attempts"]) for t in (await call("GET", "/api/v1/quiz-attempts")).json()["topics"]) == 3

    # (d) 50 per topic cap keeps the newest
    async with engine.begin() as c:
        await c.execute(text("insert into app.quiz_attempts (user_id, quiz_id, topic, score, total, created_at) "
                             "select 'C', 'q' || g, 'T', g, 100, now() + g * interval '1 second' "
                             "from generate_series(1, 60) g"))
    c_attempts = (await call("GET", "/api/v1/quiz-attempts", "C")).json()["topics"][0]["attempts"]
    assert len(c_attempts) == 50 and c_attempts[0]["score"] == 11 and c_attempts[-1]["score"] == 60

    # (e) export includes, delete removes
    exported = (await call("GET", "/api/v1/me/export")).json()
    assert len(exported["quiz_attempts"]) == 3 and {t["user_id"] for t in exported["quiz_attempts"]} == {"A"}
    assert (await call("DELETE", "/api/v1/me")).status_code == 204
    async with engine.connect() as c:
        left = dict((await c.execute(text("select user_id, count(*) from app.quiz_attempts group by 1"))).all())
    assert left == {"B": 1, "C": 60}
    await engine.dispose()


def test_quiz_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
