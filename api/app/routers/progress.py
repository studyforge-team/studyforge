"""T4: GET /api/v1/quiz-attempts — per-topic quiz attempt history.

Returns the student's quiz attempts grouped by topic, newest topic first,
oldest attempt first per topic, max 50 per topic.
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

# Fetch all attempts for the user, ordered by (latest attempt per topic DESC,
# then within each topic by created_at ASC).
_ATTEMPTS = text(
    "SELECT quiz_id, topic, score, total, marks_per_q, created_at "
    "FROM app.quiz_attempts "
    "WHERE user_id = :u "
    "ORDER BY topic, created_at ASC"
)

_LATEST_PER_TOPIC = text(
    "SELECT topic, MAX(created_at) AS latest "
    "FROM app.quiz_attempts "
    "WHERE user_id = :u "
    "GROUP BY topic "
    "ORDER BY MAX(created_at) DESC"
)


@router.get("/quiz-attempts", dependencies=[Depends(_need_db)])
async def get_quiz_attempts(user: UserDep, engine: EngineDep) -> dict[str, Any]:
    """Return per-topic attempt history for the current user."""
    async with engine.connect() as conn:
        rows = (await conn.execute(_ATTEMPTS, {"u": user})).mappings().all()
        topic_order_rows = (
            await conn.execute(_LATEST_PER_TOPIC, {"u": user})
        ).mappings().all()

    # Build topic → attempts map
    topic_map: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        topic = row["topic"]
        if topic not in topic_map:
            topic_map[topic] = []
        if len(topic_map[topic]) < 50:  # max 50 per topic
            topic_map[topic].append(
                {
                    "quiz_id": row["quiz_id"],
                    "score": row["score"],
                    "total": row["total"],
                    "marks_per_q": row["marks_per_q"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                }
            )

    # Sort topics by their latest attempt (newest first)
    ordered_topics = [r["topic"] for r in topic_order_rows]
    topics = [
        {"topic": t, "attempts": topic_map.get(t, [])}
        for t in ordered_topics
        if t in topic_map
    ]

    return {"topics": topics}
