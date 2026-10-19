"""Dashboard router — GET /api/v1/dashboard.

Returns the student's current tasks, weak topics, recent solves and
reminders.  All data is per-user, filtered by ``user_id``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.routers.checkins import _need_db, get_engine
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]

# SQL for the recent solves list (question text + status from state JSONB)
_SOLVES = text(
    "SELECT id, left(state->>'question', 200) AS question, "
    "state->>'status' AS status, updated_at "
    "FROM app.solves WHERE user_id = :u "
    "ORDER BY updated_at DESC LIMIT 5"
)

_WEAK_TOPICS = text(
    "SELECT topic, "
    "COUNT(*) AS attempts, "
    "SUM(CASE WHEN correct THEN 1 ELSE 0 END) AS correct "
    "FROM app.topic_results WHERE user_id = :u "
    "GROUP BY topic ORDER BY (SUM(CASE WHEN correct THEN 1 ELSE 0 END)::float / COUNT(*)) ASC "
    "LIMIT 5"
)


@router.get("/dashboard", dependencies=[Depends(_need_db)])
async def get_dashboard(user: UserDep, engine: EngineDep) -> dict[str, Any]:
    async with engine.connect() as conn:
        solves_rows = (await conn.execute(_SOLVES, {"u": user})).mappings().all()
        weak_rows = (await conn.execute(_WEAK_TOPICS, {"u": user})).mappings().all()

    recent_solves = [
        {
            "id": r["id"],
            "question": r["question"] or "",
            "status": r["status"] or "unknown",
            "created_at": r["updated_at"].isoformat() if r["updated_at"] else "",
        }
        for r in solves_rows
    ]
    weak_topics = [
        {
            "topic": r["topic"],
            "attempts": int(r["attempts"]),
            "correct": int(r["correct"]),
        }
        for r in weak_rows
    ]
    return {
        "tasks": [],
        "weak_topics": weak_topics,
        "recent_solves": recent_solves,
        "reminders": [],
    }
