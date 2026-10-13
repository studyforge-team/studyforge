"""The solve routes mounted on the real app: real get_deps, Postgres stores, fake model."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_loop import GOOD, FakeLLM, calc, tool

from app import auth, db, wiring
from app.main import app
from app.routers import solve

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")
CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))


async def _exercise(llm: FakeLLM, made: dict[str, Any]) -> None:
    who = {"u": "A"}
    app.dependency_overrides[solve.current_user] = lambda: who["u"]
    due = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    llm.script += [
        ("chat_json", {"kind": "calc"}),
        ("chat_tools", tool("schedule_reminder", title="Thermo exam", due_at_utc=due)),
        ("chat_tools", tool("run_python", code="result = {}")),
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/solve", json={"question": "Find X"})
        sid, step = r.json()["solve_id"], r.json()["step"]
        assert r.status_code == 200 and step["type"] == "run_python"
        assert (await c.get(f"/api/v1/solve/{sid}")).json() == {"step": step}
        body = {"stdout": "", "result": GOOD, "figures": [], "error": None, "ms": 1}
        final = (await c.post(f"/api/v1/solve/{sid}/result", json=body)).json()["step"]
        assert final["type"] == "final"
        who["u"] = "B"
        assert (await c.get(f"/api/v1/solve/{sid}")).status_code == 404

        who["u"] = "A"  # the model's schedule_reminder call reaches D6
        assert (await c.post("/api/v1/solve", json={"question": "Remind me"})).status_code == 200
    eng = db.shared_engine()
    async with eng.connect() as conn:
        owner = (await conn.execute(text("select user_id from app.solves where id=:i"), {"i": sid})).scalar()
        jobs = (await conn.execute(text("select count(*) from app.jobs where user_id='A'"))).scalar()
    assert owner == "A" and jobs and jobs >= 1
    assert type(made["recorder"]).__name__ == "PgCostRecorder" and made["budget"] is not None
    await eng.dispose()


def test_solve_mounted(monkeypatch: pytest.MonkeyPatch) -> None:
    made: dict[str, Any] = {}
    llm = calc(
        ("chat_tools", tool("run_python", code="result = {}")),
        ("chat_json", {"answer_md": "X = 0.6667"}),
    )

    def factory(registry: Any, **kw: Any) -> FakeLLM:
        made.update(kw)
        return llm

    monkeypatch.setenv("TF_API_KEY", "k")
    monkeypatch.setattr(wiring, "LLMClient", factory)
    monkeypatch.setattr(wiring, "_cache", None)
    monkeypatch.setattr(db, "_engine", None)
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise(llm, made))
    finally:
        app.dependency_overrides[solve.current_user] = auth.current_user
        command.downgrade(CFG, "base")
