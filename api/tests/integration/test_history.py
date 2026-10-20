"""T5 done-when: GET /solves pages 20 at a time, searches, and never shows another user's rows (real Postgres)."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db import make_engine, solves
from app.routers import history

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


async def _exercise() -> None:
    engine = make_engine()
    who = {"u": "A"}
    app = FastAPI()
    app.include_router(history.router)
    app.dependency_overrides[history.current_user] = lambda: who["u"]
    app.dependency_overrides[history.get_engine] = lambda: engine

    async def get(user: str, **params: str) -> Any:
        who["u"] = user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/v1/solves", params=params)
        assert r.status_code == 200
        return r.json()

    assert await get("A") == {"items": [], "next": None}  # empty

    rows = [{"id": f"a{i:02d}", "user_id": "A", "updated_at": T0 + timedelta(minutes=i),
             "state": {"question": f"Question {i} " + "x" * 300 if i == 29 else f"Question {i}",
                       "status": "done", "answer": "SECRET", "figures": ["data:image/png;base64,AAA"]}}
            for i in range(30)]
    rows += [{"id": "a-pct", "user_id": "A", "updated_at": T0 - timedelta(hours=1),
              "state": {"question": "Reach 100% yield, a_b?"}},
             {"id": "b1", "user_id": "B", "updated_at": T0 + timedelta(hours=1),
              "state": {"question": "B secret Question", "status": "done"}}]
    async with engine.begin() as conn:
        await conn.execute(solves.insert(), rows)

    p1 = await get("A")
    assert len(p1["items"]) == 20 and p1["next"] == p1["items"][-1]["updated_at"]
    assert [i["id"] for i in p1["items"]][:2] == ["a29", "a28"]  # newest first
    assert all(set(i) == {"id", "question", "status", "updated_at"} for i in p1["items"])
    assert len(p1["items"][0]["question"]) == 200 and "SECRET" not in str(p1) and "data:image" not in str(p1)
    assert "B secret" not in str(p1)

    p2 = await get("A", before=p1["next"])
    assert [i["id"] for i in p2["items"]] == [f"a{i:02d}" for i in range(9, -1, -1)] + ["a-pct"]
    assert p2["next"] is None
    assert not {i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}

    # exactly 20 rows left -> no next page
    assert (await get("A", before=(T0 + timedelta(minutes=19)).isoformat()))["next"] is None

    # search: case-insensitive; % and _ are literal; other users never match
    assert [i["id"] for i in (await get("A", q="QUESTION 2"))["items"]][:2] == ["a29", "a28"]
    assert [i["id"] for i in (await get("A", q="100%"))["items"]] == ["a-pct"]
    assert [i["id"] for i in (await get("A", q="a_b"))["items"]] == ["a-pct"]
    assert (await get("A", q="%"))["items"][0]["id"] == "a-pct" and len((await get("A", q="%"))["items"]) == 1
    assert (await get("A", q="_"))["items"][0]["id"] == "a-pct"
    assert (await get("A", q="B secret"))["items"] == []
    assert (await get("A", q="'; DROP TABLE app.solves; --"))["items"] == []

    # isolation
    assert [i["id"] for i in (await get("B"))["items"]] == ["b1"]
    assert (await get("C")) == {"items": [], "next": None}
    who["u"] = "A"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/solves", params={"q": "x" * 81})).status_code == 422
    await engine.dispose()


def test_history_done_when() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
