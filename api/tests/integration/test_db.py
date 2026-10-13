"""Runs only with DATABASE_URL set (CI service container, or a throwaway local Postgres)."""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import auth, db, spend
from app.agent.quiz import MCQItem, Quiz
from app.agent.state import SolveState
from app.db import (
    PgCostRecorder,
    PgNoticeStore,
    PgQuizStore,
    PgStateStore,
    beat,
    make_engine,
)
from app.llm.cost import CallRecord
from app.llm.errors import BudgetExceeded
from app.main import app
from app.routers import me, uploads
from tests.unit.conftest import MemoryStorage

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
TABLES = ["solves", "quizzes", "llm_calls", "heartbeats", "notices"]
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
    await _spend(engine)
    await engine.dispose()
    # one TestClient = one loop, so the lazily created db._engine is reused across both calls
    with TestClient(app) as client:
        for _ in range(2):
            r = client.get("/keepalive?source=gha")
            assert r.status_code == 200
            assert r.json()["db"] == "ok" and r.json()["wrote"] is False  # beat() above is < 60 s
    db._engine = None  # bound to that loop


async def _spend(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("delete from app.llm_calls"))
    rec = PgCostRecorder(engine)
    row = CallRecord("solver", "m", True, None, 1, 1, 1.0, 5, None)
    for uid, anon, ip in (("ua", True, "1.1.1.1"), ("ub", False, "2.2.2.2")):
        spend.who.set(spend.Who(uid, anon, ip))
        await rec.record(row)
    # an old row counts towards the total only
    async with engine.begin() as conn:
        await conn.execute(text("update app.llm_calls set created_at = now() - interval '2 days' where user_id='ub'"))

    async def hits(caps: spend.Caps, who: spend.Who) -> bool:
        spend.who.set(who)
        try:
            await spend.SpendGuard(engine, caps).check("solver", "m")
        except BudgetExceeded:
            return True
        return False

    anon, member, other = spend.Who("ua", True, "1.1.1.1"), spend.Who("ub", False, "2.2.2.2"), spend.Who("uc", False, "1.1.1.1")
    assert not await hits(spend.Caps(), anon)  # no caps: no query, no block
    assert await hits(spend.Caps(total=2.0), other)  # all-time: 1.0 today + 1.0 two days ago
    assert not await hits(spend.Caps(total=2.5), other)
    assert await hits(spend.Caps(day=1.0), other) and not await hits(spend.Caps(day=1.5), other)
    assert await hits(spend.Caps(user=1.0), anon) and not await hits(spend.Caps(user=1.0), member)  # ub's call is old
    assert await hits(spend.Caps(ip=1.0), anon)
    assert not await hits(spend.Caps(ip=1.0), spend.Who("ua", False, "1.1.1.1"))  # per-IP: anonymous only
    assert not await hits(spend.Caps(ip=1.0), spend.Who(None, True, None))

    solve = SolveState(id="c1", user_id="u1", question="Find   X", status="done", last_step={"type": "final"})
    store = PgStateStore(engine)
    await store.save(solve)
    await store.save(solve.model_copy(update={"id": "c2", "flags": ["cached"], "last_step": {"type": "bad"}}))
    assert await store.cached("find x") == {"type": "final"}
    assert await store.cached("other") is None
    spend.who.set(spend.Who())


def test_me_export_and_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_me())
    finally:
        db._engine = None
        command.downgrade(CFG, "base")


async def _me() -> None:
    engine = make_engine()
    store, quizzes, rec = PgStateStore(engine), PgQuizStore(engine), PgCostRecorder(engine)
    row = CallRecord("solver", "m", True, None, 1, 1, 0.5, 5, None)
    for uid, n in (("A", 2), ("B", 1)):
        for i in range(n):
            await store.save(SolveState(id=f"{uid}{i}", user_id=uid, question="q"))
            await quizzes.save(uid, QUIZ)
            await PgNoticeStore(engine).add(uid, {"text": "lab due Fri", "source": "paste"}, 50)
            spend.who.set(spend.Who(uid, False, "9.9.9.9"))
            await rec.record(row)
    spend.who.set(spend.Who())

    async def counts(uid: str) -> list[object]:
        return [await _scalar(f"select count(*) from app.{t} where user_id='{uid}'") for t in ("solves", "quizzes", "llm_calls", "notices")]

    sent: list[str] = []

    async def http() -> AsyncIterator[httpx.AsyncClient]:
        def ok(req: httpx.Request) -> httpx.Response:
            sent.append(str(req.url))
            return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(ok)) as c:
            yield c

    mem = MemoryStorage()
    fa, fb = "A/question-" + "a" * 32, "B/question-" + "b" * 32
    await mem.put(fa, b"x", "image/png")
    await mem.put(fb, b"y", "image/png")
    app.dependency_overrides |= {me.current_user: lambda: "A", me.get_http: http, uploads.get_storage_opt: lambda: mem}
    try:
        with TestClient(app) as client:  # one TestClient = one loop for the shared engine
            j = client.get("/api/v1/me/export").json()
            assert [len(j[t]) for t in ("solves", "quizzes", "llm_calls", "notices")] == [2, 2, 2, 2]
            assert {r["user_id"] for r in j["solves"] + j["quizzes"] + j["llm_calls"] + j["notices"]} == {"A"}
            assert [f["name"] for f in j["files"]] == [fa[2:]]
            total = await _scalar("select sum(cost_usd) from app.llm_calls")
            assert client.delete("/api/v1/me").status_code == 204
        assert sent == ["https://proj.supabase.co/auth/v1/admin/users/A"]
    finally:
        app.dependency_overrides[me.current_user] = auth.current_user
        app.dependency_overrides.pop(me.get_http, None)
        app.dependency_overrides.pop(uploads.get_storage_opt, None)
    assert list(mem.objs) == [fb]  # A's files gone, B's kept
    assert await counts("A") == [0, 0, 0, 0] and await counts("B") == [1, 1, 1, 1]
    assert await _scalar("select count(*) from app.llm_calls where user_id is null and ip is null") == 2
    assert await _scalar("select sum(cost_usd) from app.llm_calls") == total  # spend accounting intact
    await engine.dispose()
