"""T1 on a real Postgres: a quiz made by POST /quizzes is stored and accepted by POST /quizzes/{id}/answers.
Runs only with DATABASE_URL set."""

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app import db
from app.db import make_engine
from app.main import app
from app.routers import checkins, prep, solve, uploads

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")
CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))


def _mcq(i: int) -> dict[str, Any]:
    return {"type": "mcq", "topic": "CSTR", "stem": f"Question {i}?", "options": ["a", "b", "c", "d"],
            "correct_index": 0, "misconceptions": {"1": "m", "2": "m", "3": "m"}, "explanation": "e"}


_BLANK = {"type": "blank", "topic": "CSTR", "stem": "A CSTR is ____.", "answers": ["well mixed"], "explanation": "e"}


class FakeLLM:
    calls = 0  # quizzes are written in parallel batches: each call gets new stems, or de-dupe leaves too few

    async def chat_json(self, role: str, messages: list[Any], schema: type[Any], **_: Any) -> tuple[Any, Any]:
        k, self.calls = self.calls, self.calls + 1
        return schema(title="CSTR quiz", items=[_mcq(2 * k), _mcq(2 * k + 1), _BLANK]), None


def test_quiz_route_then_answers() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        db._engine = None
        command.downgrade(CFG, "base")


async def _exercise() -> None:
    engine = make_engine()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides |= {solve.current_user: lambda: "A", checkins.get_engine: lambda: engine,
                                 prep.get_llm: lambda: FakeLLM(), uploads.get_storage_opt: lambda: None}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/api/v1/quizzes", json={"topic": "CSTR", "n_items": 3, "kinds": "mixed", "marks_per_q": 2})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total_marks"] == 6 and body["suggested_minutes"] == 9 and len(body["items"]) == 3
            async with engine.connect() as conn:
                stored = (await conn.execute(text("select quiz from app.quizzes where id = :i and user_id = 'A'"),
                                             {"i": body["id"]})).scalar()
            assert stored["items"] == body["items"] and stored["topic"] == "CSTR" and stored["marks_per_q"] == 2
            ans = {"answers": ["0", "0", "well mixed"], "score": 3, "correct": [True, False, None]}
            r = await c.post(f"/api/v1/quizzes/{body['id']}/answers", json=ans)
            assert r.status_code == 200 and r.json() == {"recorded": 2}, r.text
            app.dependency_overrides[solve.current_user] = lambda: "B"  # another student's quiz: not found
            assert (await c.post(f"/api/v1/quizzes/{body['id']}/answers", json=ans)).status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
    await engine.dispose()
