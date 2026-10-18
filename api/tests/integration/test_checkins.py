"""D7 done-when: right -> done; wrong/ignored -> follow-up next day (fake clock, real Postgres)."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import make_engine
from app.reminders import checkin_text, drain, schedule, sweep
from app.routers import checkins

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
DEADLINE = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)  # Fri 30 Oct 22:30 IST
NOW = datetime(2026, 10, 20, tzinfo=UTC)
CHECKIN = DEADLINE + timedelta(hours=1, minutes=1)
DAY = timedelta(days=1)


async def _exercise() -> None:
    engine = make_engine()
    user = {"u": "A"}
    clock = {"t": CHECKIN}
    app = FastAPI()
    app.include_router(checkins.router)
    app.dependency_overrides[checkins.current_user] = lambda: user["u"]
    app.dependency_overrides[checkins.get_engine] = lambda: engine
    app.dependency_overrides[checkins.now] = lambda: clock["t"]

    async def post(job_id: int, correct: bool, who: str = "A"):  # type: ignore[no-untyped-def]
        user["u"] = who
        # httpx ASGI client, not TestClient: TestClient runs the app on its own loop, which can't share this engine
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.post(f"/api/v1/checkins/{job_id}", json={"correct": correct})

    async def one(t: datetime) -> dict:  # type: ignore[type-arg]
        got = [r for r in await drain(engine, t) if r["payload"]["slot"].startswith("checkin")]
        assert len(got) == 1
        return got[0]

    # each task: schedule, deliver all reminders and the round-1 check-in
    for who, title in (("A", "Right"), ("A", "Wrong"), ("A", "Ignored")):
        assert await schedule(engine, who, title, DEADLINE, NOW) == 4  # 3 reminders + check-in
        await drain(engine, CHECKIN - timedelta(hours=2))  # reminders
    # drain at CHECKIN delivers all three round-1 check-ins
    got = {r["payload"]["title"]: r for r in await drain(engine, CHECKIN)}
    assert set(got) == {"Right", "Wrong", "Ignored"}
    assert "?checkin=" in checkin_text(got["Right"]["payload"], got["Right"]["id"])

    # (a) RIGHT -> done, pending reminders gone, nothing more delivered
    right = got["Right"]["id"]
    async with engine.begin() as c:  # an unsent follow-up for this task must be deleted
        await c.execute(text(
            "INSERT INTO app.jobs (user_id,kind,dedupe_key,due_at,payload) "
            "SELECT user_id,'reminder',CONCAT(payload->>'task',chr(58),'extra'),:d,'{}' "
            "FROM app.jobs WHERE id=:i"), {"d": CHECKIN + DAY, "i": right})
    r = await post(right, True)
    assert r.status_code == 200 and r.json() == {"done": True, "follow_up_at": None}
    assert (await post(right, True)).status_code == 409  # twice
    assert (await post(right, False)).status_code == 409
    assert (await post(got["Wrong"]["id"], True, "B")).status_code == 404  # B can't touch A's job
    assert (await post(999999, True)).status_code == 404
    async with engine.connect() as c:
        done = (await c.execute(text("SELECT payload->>'done' FROM app.jobs WHERE id=:i"), {"i": right})).scalar()
        left = (await c.execute(text(
            "SELECT count(*) FROM app.jobs WHERE sent_at IS NULL AND payload->>'title'='Right'"))).scalar()
    assert done == "true" and left == 0

    # (b) WRONG -> round 2 due +24 h, delivered once, not before
    r = await post(got["Wrong"]["id"], False)
    due2 = CHECKIN + DAY
    assert r.json() == {"done": False, "follow_up_at": due2.isoformat()}
    assert [x for x in await drain(engine, due2 - timedelta(minutes=1)) if x["payload"]["title"] == "Wrong"] == []
    clock["t"] = due2 + timedelta(minutes=1)
    r2 = [x for x in await drain(engine, clock["t"]) if x["payload"]["title"] == "Wrong"]
    assert [x["payload"]["round"] for x in r2] == [2]
    assert [x for x in await drain(engine, clock["t"]) if x["payload"]["title"] == "Wrong"] == []

    # (c) IGNORED -> sweep creates round 2 only after 24 h, once; round 3 is the cap
    assert await sweep(engine, CHECKIN + timedelta(hours=23)) == 0
    t2 = CHECKIN + DAY + timedelta(minutes=1)
    # Wrong's round 2 was sent at due2+1m (= t2) so it is not yet 24 h old; only Ignored qualifies
    assert await sweep(engine, t2) == 1
    assert await sweep(engine, t2) == 0  # repeat -> still once
    nxt = [x for x in await drain(engine, t2) if x["payload"]["title"] == "Ignored"]
    assert [x["payload"]["round"] for x in nxt] == [2]
    t3 = t2 + DAY
    assert await sweep(engine, t3) == 2  # Ignored r2 -> r3 ; Wrong r2 (sent t2) -> r3
    assert len(await drain(engine, t3)) == 2
    assert await sweep(engine, t3 + DAY) == 0  # round 3 ignored: no round 4
    # round 3 wrong: no follow-up either
    async with engine.connect() as c:
        r3 = (await c.execute(text(
            "SELECT id FROM app.jobs WHERE payload->>'title'='Wrong' AND (payload->>'round')::int=3"))).scalar()
    clock["t"] = t3 + DAY
    assert (await post(r3, False)).json() == {"done": False, "follow_up_at": None}
    assert await sweep(engine, t3 + 3 * DAY) == 0

    # (d) LATE RIGHT: round 1 ignored, round 2 out, then round 1 answered right -> no round 3
    d2, c2 = DEADLINE + 10 * DAY, CHECKIN + 10 * DAY
    assert await schedule(engine, "C", "Late", d2, NOW) == 4
    late = [x for x in await drain(engine, c2) if x["payload"]["title"] == "Late"]
    late1 = next(x["id"] for x in late if x["payload"]["slot"] == "checkin-1")
    assert await sweep(engine, c2 + DAY + timedelta(minutes=1)) == 1
    assert len(await drain(engine, c2 + DAY + timedelta(minutes=1))) == 1  # round 2 delivered
    clock["t"] = c2 + DAY + timedelta(minutes=5)
    assert (await post(late1, True, "C")).json()["done"] is True
    assert await sweep(engine, c2 + 2 * DAY + timedelta(minutes=10)) == 0  # done: never nag again

    async with engine.connect() as c:
        assert (await c.execute(text(
            "select relrowsecurity from pg_class where oid='app.jobs'::regclass"))).scalar() is True
    await engine.dispose()


def test_checkins_done_when() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
