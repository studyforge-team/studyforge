"""Quiz answers router — POST /api/v1/quizzes/{quiz_id}/answers.

This is the *existing* answers endpoint.  It records per-topic results
and (T4) inserts a ``quiz_attempts`` row inside the same transaction.

The response stays ``{"recorded": n}`` where *n* is the non-skipped item count.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import quiz_attempts, quizzes
from app.routers.checkins import _need_db, get_engine
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]


class AnswerBody(BaseModel):
    answers: list[int | str | None]
    score: float
    correct: list[bool | None]


@router.post("/quizzes/{quiz_id}/answers", dependencies=[Depends(_need_db)])
async def save_answers(
    quiz_id: str,
    body: AnswerBody,
    user: UserDep,
    engine: EngineDep,
) -> dict[str, Any]:
    """Record per-topic results for each answered item.

    ``body.correct`` entries may be ``null`` (skipped item).
    Returns ``{"recorded": n}`` where *n* is the number of non-skipped items.
    """
    # Load the quiz to get item topics and metadata.
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                quizzes.select().where(
                    quizzes.c.id == quiz_id,
                    quizzes.c.user_id == user,
                )
            )
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="quiz not found")

    quiz: dict[str, Any] = dict(row._mapping)["quiz"]  # type: ignore[index]
    items: list[dict[str, Any]] = quiz.get("items", [])

    seen: list[bool] = []
    async with engine.begin() as conn:
        for i, correct in enumerate(body.correct):
            if correct is None:
                continue  # skipped
            if i >= len(items):
                break
            topic = items[i].get("topic", quiz.get("title", "Quiz"))
            await conn.execute(
                text(
                    "INSERT INTO app.topic_results (user_id, topic, correct) "
                    "VALUES (:u, :t, :c)"
                ),
                {"u": user, "t": topic, "c": bool(correct)},
            )
            seen.append(bool(correct))

        # ── T4: insert quiz_attempts row ──────────────────────────────────
        await conn.execute(
            quiz_attempts.insert().values(
                user_id=user,
                quiz_id=quiz_id,
                topic=str(quiz.get("topic") or quiz.get("title") or "Quiz")[:80],
                score=body.score,
                total=float(sum(c is not None for c in body.correct)),
                marks_per_q=float(quiz.get("marks_per_q") or 1),
            )
        )

    return {"recorded": len(seen)}
