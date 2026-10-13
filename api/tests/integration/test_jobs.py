"""D6 done-when: fake-clock test, T-3d / T-1d / morning-of fire once each."""

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import main
from app.db import make_engine
from app.main import app
from app.reminders import drain, schedule, schedule_reminder_tool

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
DEADLINE = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)  # Fri 30 Oct 22:30 IST


def at(d: int, h: int = 0, m: int = 0) -> datetime:
    return datetime(2026, 10, d, h, m, tzinfo=UTC)


async def _slots(engine, now: datetime) -> list[str]:  # type: ignore[no-untyped-def]
    return [r["payload"]["slot"] for r in await drain(engine, now)]


async def _exercise() -> None:
    engine = make_engine()
    assert await schedule(engine, "u1", "OS exam", DEADLINE, at(20)) == 3
    assert await schedule(engine, "u1", " os  EXAM ", DEADLINE, at(20)) == 0  # dedupe
    assert await _slots(engine, at(26)) == []
    assert await _slots(engine, at(27, 17, 1)) == ["t-3d"]
    assert await _slots(engine, at(27, 17, 1)) == []  # fires once
    assert await _slots(engine, at(29, 17, 1)) == ["t-1d"]
    assert await _slots(engine, at(30, 2, 31)) == ["morning"]
    assert await _slots(engine, at(31)) == []

    # concurrent pingers: one due job is delivered exactly once
    await schedule(engine, "u2", "Maths", DEADLINE, at(29, 18))  # only "morning" left
    got = await asyncio.gather(*(drain(engine, at(30, 3)) for _ in range(2)))
    assert sum(len(g) for g in got) == 1

    msg = await schedule_reminder_tool(engine, "u3", "Chem", DEADLINE.isoformat(), at(20))
    assert msg == "scheduled 3 reminders (3 days before, 1 day before, morning of)"

    async with engine.connect() as conn:
        assert (await conn.execute(text(
            "select relrowsecurity from pg_class where oid='app.jobs'::regclass"
        ))).scalar() is True
    await engine.dispose()


def test_fake_clock_and_keepalive() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
        with TestClient(app) as client:
            r = client.get("/keepalive?source=gha")
            assert r.status_code == 200 and isinstance(r.json()["sent"], int)
        main._engine = None  # bound to that loop
    finally:
        command.downgrade(CFG, "base")
