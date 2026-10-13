"""Runs only with DATABASE_URL set (CI service container, or a throwaway local Postgres)."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import main
from app.agent.quiz import MCQItem, Quiz
from app.agent.state import SolveState
from app.db import PgCostRecorder, PgQuizStore, PgStateStore, beat, make_engine
from app.llm.cost import CallRecord
from app.main import app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
TABLES = ["solves", "quizzes", "llm_calls", "heartbeats"]
QUIZ = Quiz(
    title="t",
    items=[
        MCQItem(
            type="mcq", topic="t", stem="s", options=["a", "b", "c", "d"], correct_index=0,
            misconceptions={1: "x", 2: "y", 3: "z"}, explanation="e",
        )
    ],
)


async def _scalar(sql: str) -> object:
    engine = make_engine()
    async with engine.connect() as conn:
        value = (await conn.execute(text(sql))).scalar()
    await engine.dispose()
    return value


def test_migrations_and_stores() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
    assert asyncio.run(_scalar("select count(*) from pg_tables where schemaname='app' and tablename<>'alembic_version'")) == 0


async def _exercise() -> None:
    engine = make_engine()
    store = PgStateStore(engine)

    state = SolveState(id="s1", user_id="u1", question="q")
    await store.save(state)
    assert await store.get("s1") == state
    assert await store.get("missing") is None

    async def bump() -> None:
        for _ in range(10):
            async with store.lock("s1"):
                s = await store.get("s1")
                assert s is not None
                s.steps_used += 1
                await store.save(s)

    await asyncio.gather(bump(), bump())
    got = await store.get("s1")
    assert got is not None and got.steps_used == 20

    quiz_id = await PgQuizStore(engine).save("u1", QUIZ)
    await PgCostRecorder(engine).record(
        CallRecord("planner", "m", True, None, 1, 2, None, 5, "s1")
    )
    async with engine.connect() as conn:
        row = (await conn.execute(text("select user_id from app.quizzes where id=:i"), {"i": quiz_id})).one()
        assert row[0] == "u1"
        n = (await conn.execute(text("select count(*) from app.llm_calls"))).scalar()
        assert n == 1
        rls = (await conn.execute(text(
            "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='app' and c.relkind='r' and c.relrowsecurity"
        ))).scalar()
        assert rls == len(TABLES)
    assert await beat(engine, "t") is True
    assert await beat(engine, "t") is False  # rate-limited to one per 60 s
    async with engine.connect() as conn:
        assert (await conn.execute(text("select count(*) from app.heartbeats"))).scalar() == 1
    await engine.dispose()
    # one TestClient = one loop, so the lazily created main._engine is reused across both calls
    with TestClient(app) as client:
        for _ in range(2):
            r = client.get("/keepalive?source=gha")
            assert r.status_code == 200
            assert r.json()["db"] == "ok" and r.json()["wrote"] is False  # beat() above is < 60 s
    main._engine = None  # bound to that loop
