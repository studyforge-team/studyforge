"""E1: GET /api/v1/dashboard, the wire shape of web/src/api/types.ts `Dashboard`."""

import os
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.reminders import checkin_text, reminder_text
from app.routers.checkins import get_engine, now
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

# one row per task (checkin rows carry payload.task); done if any round was answered right
_TASKS = text(
    "SELECT payload->>'task' AS id, max(payload->>'title') AS title, "
    "max((payload->>'deadline_utc')::timestamptz) AS due, bool_or(payload->>'done' = 'true') AS done "
    "FROM app.jobs WHERE user_id = :u AND payload->>'task' IS NOT NULL GROUP BY 1 "
    "HAVING max((payload->>'deadline_utc')::timestamptz) >= "
    "CASE WHEN bool_or(payload->>'done' = 'true') THEN CAST(:done_from AS timestamptz) "
    "ELSE CAST(:open_from AS timestamptz) END ORDER BY due LIMIT 20"
)
_SOLVES = text(
    "SELECT id, left(state->>'question', 200) AS question, state->>'status' AS status, updated_at "
    "FROM app.solves WHERE user_id = :u ORDER BY updated_at DESC LIMIT 5"
)
_INBOX = text(
    "SELECT id, kind, payload, due_at, sent_at FROM app.jobs "
    "WHERE user_id = :u AND sent_at IS NOT NULL ORDER BY sent_at DESC, id DESC LIMIT 30"
)


def _need_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(status_code=503, detail="database not configured")


@router.get("/dashboard", dependencies=[Depends(_need_db)])
async def dashboard(
    user: Annotated[str, Depends(current_user)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    at: Annotated[datetime, Depends(now)],
) -> dict[str, Any]:
    args = {"u": user}
    async with engine.connect() as c:
        tasks = (await c.execute(_TASKS, {**args, "open_from": at - timedelta(days=1),
                                          "done_from": at - timedelta(days=2)})).mappings().all()
        solves = (await c.execute(_SOLVES, args)).mappings().all()
        inbox = (await c.execute(_INBOX, args)).mappings().all()
    return {
        "tasks": [{"id": t["id"], "title": t["title"], "action": "Open prep pack",
                   "due_at_utc": t["due"].isoformat(), "source": "reminder",
                   "status": "done" if t["done"] else "open"} for t in tasks],
        "weak_topics": [],  # D8 (topic stats) is not built yet
        "recent_solves": [{"id": s["id"], "question": s["question"] or "", "status": s["status"] or "",
                           "created_at": s["updated_at"].isoformat()}  # no created_at column: last update
                          for s in solves],
        "reminders": [{"id": str(r["id"]), "channel": "app",  # push is D1b
                       "title": checkin_text(r["payload"], r["id"]) if r["kind"] == "checkin"
                       else reminder_text(r["payload"]),
                       "due_at_utc": r["due_at"].isoformat(), "sent_at": r["sent_at"].isoformat()}
                      for r in inbox],
    }
