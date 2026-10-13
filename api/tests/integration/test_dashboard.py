"""E1 done-when: a fired reminder shows in the dashboard inbox, tasks/solves are per user (real Postgres)."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.agent.state import SolveState
from app.db import PgStateStore, make_engine
from app.reminders import checkin_text, drain, reminder_text, schedule
from app.routers import checkins, dashboard

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
DEADLINE = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 20, tzinfo=UTC)
T3D = DEADLINE - timedelta(days=3)
CHECKIN = DEADLINE + timedelta(hours=1, minutes=1)
KEYS = {
    "tasks": {"id", "title", "action", "due_at_utc", "source", "status"},
    "recent_solves": {"id", "question", "status", "created_at"},
    "reminders": {"id", "title", "due_at_utc", "sent_at", "channel"},
}


async def _exercise() -> None:
    engine = make_engine()
    who = {"u": "A"}
    clock = {"t": T3D + timedelta(minutes=1)}
    app = FastAPI()
    app.include_router(dashboard.router)
    app.include_router(checkins.router)
    app.dependency_overrides[dashboard.current_user] = lambda: who["u"]
    app.dependency_overrides[dashboard.get_engine] = lambda: engine
    app.dependency_overrides[dashboard.now] = lambda: clock["t"]

    async def get(user: str) -> dict:  # type: ignore[type-arg]
        who["u"] = user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/v1/dashboard")
        assert r.status_code == 200
        return r.json()  # type: ignore[no-any-return]

    assert await schedule(engine, "A", "Thermo exam", DEADLINE, NOW) == 4
    assert await schedule(engine, "B", "B secret", DEADLINE, NOW) == 4
    fired = await drain(engine, clock["t"])  # T-3d for both users
    mine = next(r for r in fired if r["user_id"] == "A")
    await PgStateStore(engine).save(SolveState(id="sa", user_id="A", question="Q" * 300))
    await PgStateStore(engine).save(SolveState(id="sb", user_id="B", question="B question"))

    d = await get("A")
    assert set(d) == {"tasks", "weak_topics", "recent_solves", "reminders"} and d["weak_topics"] == []
    assert [r["title"] for r in d["reminders"]] == [reminder_text(mine["payload"])]  # sent only, no B
    assert all(set(r) == KEYS["reminders"] for r in d["reminders"])
    assert d["reminders"][0]["sent_at"] and d["reminders"][0]["channel"] == "app"
    [task] = d["tasks"]
    assert set(task) == KEYS["tasks"] and task["status"] == "open" and task["title"] == "Thermo exam"
    assert task["due_at_utc"] == DEADLINE.isoformat() and task["action"] == "Open prep pack"
    [solve] = d["recent_solves"]
    assert set(solve) == KEYS["recent_solves"] and solve["id"] == "sa" and len(solve["question"]) == 200
    assert "B secret" not in str(d) and "B question" not in str(d)
    assert (await get("B"))["recent_solves"][0]["id"] == "sb"

    # check-in delivered -> in the inbox with its link; answered right -> task done
    clock["t"] = CHECKIN
    ci = next(r for r in await drain(engine, CHECKIN) if r["user_id"] == "A" and r["payload"]["slot"] == "checkin-1")
    d = await get("A")
    assert d["reminders"][0]["title"] == checkin_text(ci["payload"], ci["id"])
    assert len(d["reminders"]) == 4 and d["tasks"][0]["status"] == "open"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post(f"/api/v1/checkins/{ci['id']}", json={"correct": True})).status_code == 200
    assert (await get("A"))["tasks"][0]["status"] == "done"

    # windows: done task drops after 2 days
    clock["t"] = DEADLINE + timedelta(days=3)
    assert (await get("A"))["tasks"] == []
    await engine.dispose()


def test_dashboard_done_when() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
