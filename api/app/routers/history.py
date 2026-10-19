"""T5: GET /api/v1/solves — paginated history of solved questions.

Returns a chat-list style view: question text (truncated), status, and
``updated_at``.  Supports cursor-based pagination via ``before`` and
optional text search via ``q``.

Never returns ``state``, figures or answers in the list — only the
question text and status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]

# 21 rows: if 21 returned, drop the last and set next = items[-1]['updated_at']
_LIST = text(
    "SELECT id, left(state->>'question', 200) AS question, "
    "state->>'status' AS status, updated_at "
    "FROM app.solves WHERE user_id = :u "
    "AND (CAST(:before AS timestamptz) IS NULL OR updated_at < CAST(:before AS timestamptz)) "
    "AND (CAST(:q AS text) IS NULL OR state->>'question' ILIKE '%' || CAST(:q AS text) || '%' ESCAPE '\\') "
    "ORDER BY updated_at DESC LIMIT 21"
)


def _escape_like(q: str) -> str:
    """Escape ILIKE special characters so user input is treated as literal."""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/solves", dependencies=[Depends(_need_db)])
async def list_solves(
    user: UserDep,
    engine: EngineDep,
    before: datetime | None = None,
    q: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    """Return paginated solve history for the current user.

    ``before`` is a cursor: only solves updated before this ISO datetime are
    returned.  ``q`` is a case-insensitive substring search on the question.
    ``next`` in the response is the ``updated_at`` of the last item (to pass
    as ``before`` on the next page), or ``null`` when there are no more pages.
    """
    before_str = before.isoformat() if before else None
    q_escaped = _escape_like(q) if q else None

    async with engine.connect() as conn:
        rows = (
            await conn.execute(_LIST, {"u": user, "before": before_str, "q": q_escaped})
        ).mappings().all()

    has_more = len(rows) == 21
    page = list(rows[:20])

    items = [
        {
            "id": row["id"],
            "question": row["question"] or "",
            "status": row["status"] or "unknown",
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in page
    ]

    next_cursor = (
        items[-1]["updated_at"] if has_more and items else None
    )

    return {"items": items, "next": next_cursor}
