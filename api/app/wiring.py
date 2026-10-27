"""Production Deps for the solve routes (the app overrides solve.get_deps with get_deps)."""

import functools
import os
import time

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine

from app import db
from app.agent.loop import Deps
from app.agent.quiz_gen import QuizService
from app.agent.tools import StubTools
from app.llm.client import LLMClient
from app.llm.registry import load_registry
from app.reminders import schedule_reminder_tool
from app.spend import Caps, SpendGuard


class DbTools(StubTools):
    """Reminders and quizzes are real; notes search (NR) and web search (S4) stay stubs."""

    def __init__(self, engine: AsyncEngine, llm: LLMClient) -> None:
        self._engine = engine
        self._quiz = QuizService(llm, db.PgQuizStore(engine))  # never raises

    async def schedule_reminder(self, user_id: str, title: str, due_at_utc: str) -> str:
        return await schedule_reminder_tool(self._engine, user_id, title, due_at_utc)

    async def make_quiz(self, user_id: str, topic: str, n_items: int) -> str:
        return await self._quiz.make_quiz(user_id, topic, n_items)


# One Deps (one LLM client, one httpx pool) for the process, never one per request.
# Keyed on the engine object: it holds the engine, and tests swap db._engine per event
# loop (asyncpg connections are loop-bound), so a new engine means a new Deps.
_cache: tuple[object, Deps] | None = None
# parsed once; the env-key check still runs on every request
_registry = functools.cache(load_registry)


def get_deps() -> Deps:
    global _cache
    registry = _registry()
    if not os.environ.get("DATABASE_URL") or not os.environ.get(registry.api_key_env):
        raise HTTPException(status_code=503, detail="solver not available")
    engine = db.shared_engine()
    if _cache is None or _cache[0] is not engine:
        guard = SpendGuard(engine, Caps.from_env())
        llm = LLMClient(
            registry, recorder=db.PgCostRecorder(engine), budget=guard,
            primary_spent=guard.primary_spent,
        )
        # read_upload=None until C1/C2 merge; guard keeps its Deps default
        _cache = (engine, Deps(
            llm=llm, store=db.PgStateStore(engine), clock=time.monotonic,
            tools=DbTools(engine, llm),
            # ponytail: templates are unverified single-method answers (2/6 wrong picks shown high);
            # the ChemLab page still uses them; turn back on only behind a verify step.
            templates=None,
        ))
    return _cache[1]


def prep_llm() -> LLMClient | None:
    """D5: the model for building a prep pack, or None (no key or no database). A stored pack
    opens without it; app/routers/prep.py answers 503 only when a new pack must be built."""
    try:
        return get_deps().llm  # type: ignore[return-value]
    except Exception:  # noqa: BLE001 - no key, no database, a bad registry: all mean "no model" (503)
        return None
