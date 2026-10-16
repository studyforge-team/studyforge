"""D5 prep pack on a real Postgres with a fake model: built once when opened, 5 questions each linked
to the student's own notes page, kept for later opens. Runs only with DATABASE_URL set."""

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

from app import db, reminders, spend
from app import prep as prep_mod
from app.agent.quiz import MCQItem, Quiz
from app.db import make_engine, note_chunks
from app.llm.errors import BudgetExceeded, ModelUnavailable
from app.main import app
from app.routers import checkins, prep, solve

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")
CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
NOTES = "notes-" + "a" * 32
PAGES = [  # page i+1
    "Log mean temperature difference LMTD for a heat exchanger: Q equals U A times LMTD, counter-current flow.",
    "Overall heat transfer coefficient U from film coefficients and fouling resistances in series.",
    "Shell and tube exchanger: tube passes, baffles, the F correction factor for multipass exchangers.",
    "Effectiveness NTU method: number of transfer units, heat capacity ratio, exchanger effectiveness.",
    "Fouling factors reduce the overall coefficient over time; cleaning schedules for exchangers.",
]
STEMS = [  # question i should link to page i+1
    "What does the log mean temperature difference measure in a counter-current exchanger?",
    "How do film coefficients and fouling resistances combine into the overall coefficient U?",
    "Why does a multipass shell and tube exchanger need the F correction factor?",
    "In the effectiveness NTU method, what does the number of transfer units describe?",
    "Quantum chromodynamics of gluons",  # nothing in the notes: no link
]


def _quiz(stems: list[str]) -> Quiz:
    return Quiz(title="x", items=[MCQItem(
        type="mcq", topic="Heat exchangers", stem=s, options=["a", "b", "c", "d"], correct_index=0,
        misconceptions={1: "m1", 2: "m2", 3: "m3"}, explanation="e") for s in stems])


class FakeLLM:
    def __init__(self, quiz: Quiz) -> None:
        self.quiz, self.calls, self.prompts, self.who = quiz, 0, [], []  # type: list[Any]

    async def chat_json(self, role: str, messages: list[Any], schema: type[Any], **_: Any) -> tuple[Any, Any]:
        self.calls += 1
        self.prompts.append(messages[-1]["content"])
        self.who.append(spend.who.get().user_id)  # whose caps and cost rows this call counts against
        await asyncio.sleep(0.05)  # long enough for a second, simultaneous open to arrive
        return self.quiz, None


def test_prep_pack() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        db._engine = None
        command.downgrade(CFG, "base")


async def _exercise() -> None:
    engine = make_engine()
    now = datetime.now(UTC)
    await reminders.schedule(engine, "A", "Heat exchanger assignment", now + timedelta(days=5), now)
    await reminders.schedule(engine, "A", "Quantum homework", now + timedelta(days=5), now)
    async with engine.begin() as conn:
        await conn.execute(note_chunks.insert(), [
            {"user_id": "A", "upload_id": NOTES, "page": i + 1, "text": t} for i, t in enumerate(PAGES)])
        keys = {r[0]: r[1].removeprefix("/#prep/") for r in (await conn.execute(text(
            "SELECT DISTINCT payload->>'title', payload->>'prep' FROM app.jobs"))).all()}
    hx, qm = keys["Heat exchanger assignment"], keys["Quantum homework"]
    fake = FakeLLM(_quiz(STEMS))
    who: dict[str, Any] = {"u": "A", "llm": fake}
    saved = dict(app.dependency_overrides)
    app.dependency_overrides |= {solve.current_user: lambda: who["u"], checkins.get_engine: lambda: engine,
                                 prep.get_llm: lambda: who["llm"]}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r, r2 = await asyncio.gather(c.get(f"/api/v1/prep/{hx}"), c.get(f"/api/v1/prep/{hx}"))  # two tabs at once
            assert r.status_code == r2.status_code == 200, r.text
            body = r.json()
            assert r2.json() == body and fake.calls == 1  # one build, not two
            assert fake.who == ["A"]  # the student's own spend caps and cost rows
            assert body["task"]["title"] == "Heat exchanger assignment" and body["quiz_id"] == f"prep-{hx}"
            assert len(body["quiz"]["items"]) == 5
            assert body["links"] == [{"upload_id": NOTES, "page": p} for p in (1, 2, 3, 4)] + [None]
            assert "LMTD" in fake.prompts[0]  # the student's notes went to the model as quoted data
            # opened again, even with the model gone: the stored pack, no new model call
            who["llm"] = None
            again = await c.get(f"/api/v1/prep/{hx}")
            assert again.status_code == 200 and again.json() == body and fake.calls == 1
            # a task with no stored pack and no model: 503, never a made-up pack
            assert (await c.get(f"/api/v1/prep/{qm}")).status_code == 503

            class Down(FakeLLM):
                async def chat_json(self, *a: Any, **k: Any) -> tuple[Any, Any]:
                    self.calls += 1
                    raise exc

            # failures: nothing stored; then a minute of 503 without calling the model again
            for exc, code in ((ModelUnavailable("down"), 502), (BudgetExceeded("cap"), 429)):
                prep_mod._failed.clear()
                who["llm"] = down = Down(fake.quiz)
                assert (await c.get(f"/api/v1/prep/{qm}")).status_code == code
                assert (await c.get(f"/api/v1/prep/{qm}")).status_code == 503 and down.calls == 1
            prep_mod._failed.clear()
            who["llm"] = FakeLLM(_quiz(STEMS[:3]))  # fewer than 5 usable questions: refused, not stored
            assert (await c.get(f"/api/v1/prep/{qm}")).status_code == 502
            prep_mod._failed.clear()
            who["llm"] = fake
            # another student, or a key that is no task: 404 before any model call
            who["u"] = "B"
            assert (await c.get(f"/api/v1/prep/{hx}")).status_code == 404
            who["u"] = "A"
            for bad in ("0" * 16, "xyz", "0" * 17):
                assert (await c.get(f"/api/v1/prep/{bad}")).status_code == 404
            assert fake.calls == 1
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
    async with engine.connect() as conn:  # the pack is an ordinary quiz row: covered by export/delete
        assert (await conn.execute(text("select user_id from app.quizzes where id = :i"), {"i": f"prep-{hx}"})).scalar() == "A"
    await engine.dispose()
