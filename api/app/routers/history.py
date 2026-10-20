"""T5: GET /api/v1/solves, the student's own solve history, newest first, 20 per page."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

PAGE = 20
# the question expression is the dashboard's; never selects state, figures or answers
_LIST = text(
    "SELECT id, left(state->>'question', 200) AS question, state->>'status' AS status, updated_at "
    "FROM app.solves WHERE user_id = :u "
    "AND (CAST(:before AS timestamptz) IS NULL OR updated_at < CAST(:before AS timestamptz)) "
    "AND (CAST(:q AS text) IS NULL OR state->>'question' ILIKE '%' || CAST(:q AS text) || '%' ESCAPE '\\') "
    "ORDER BY updated_at DESC LIMIT 21"
)


@router.get("/solves", dependencies=[Depends(_need_db)])
async def list_solves(
    user: Annotated[str, Depends(current_user)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    before: datetime | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> dict[str, Any]:
    if before is not None and before.tzinfo is None:
        before = before.replace(tzinfo=UTC)  # a bare time is UTC, like every other time in the API
    like = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") if q else None
    async with engine.connect() as c:
        rows = (await c.execute(_LIST, {"u": user, "before": before, "q": like})).mappings().all()
    items = [{"id": r["id"], "question": r["question"] or "", "status": r["status"] or "",
              "updated_at": r["updated_at"].isoformat()} for r in rows[:PAGE]]
    return {"items": items, "next": items[-1]["updated_at"] if len(rows) > PAGE else None}
