"""T4: GET /api/v1/quiz-attempts. A student's saved quiz results, grouped per topic (owner only)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

# newest 50 per topic, then returned oldest first; topics ordered by their latest attempt
_ATTEMPTS = text(
    "SELECT topic, quiz_id, score, total, marks_per_q, created_at FROM ("
    " SELECT *, row_number() OVER (PARTITION BY topic ORDER BY created_at DESC, id DESC) AS rn"
    " FROM app.quiz_attempts WHERE user_id = :u) t WHERE rn <= 50 ORDER BY created_at, id"
)


@router.get("/quiz-attempts", dependencies=[Depends(_need_db)])
async def quiz_attempts(
    user: Annotated[str, Depends(current_user)], engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, Any]:
    async with engine.connect() as conn:
        rows = (await conn.execute(_ATTEMPTS, {"u": user})).mappings().all()
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for r in rows:  # oldest first overall, so each topic's list is oldest first too
        by_topic.setdefault(r["topic"], []).append({
            "quiz_id": r["quiz_id"], "score": r["score"], "total": r["total"],
            "marks_per_q": r["marks_per_q"], "created_at": r["created_at"],
        })
    ordered = sorted(by_topic.items(), key=lambda kv: kv[1][-1]["created_at"], reverse=True)
    return {"topics": [{"topic": t, "attempts": a} for t, a in ordered]}
