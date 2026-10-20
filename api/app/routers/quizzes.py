"""D8: POST /api/v1/quizzes/{quiz_id}/answers. Topics come from the stored quiz, never the client."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app import topics
from app.db import quiz_attempts, quizzes
from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")


class Answers(BaseModel):
    # accepted but not stored: the server only needs `correct`. Cap is generous because subjective
    # items send free text, and a 422 here is swallowed by the web client (quiz results lost).
    answers: list[Annotated[str, Field(max_length=4000)]] = Field(max_length=20)
    score: float = Field(ge=0)  # float, not int: subjective items score fractionally
    correct: list[bool | None] = Field(max_length=20)  # None = skipped item, never seen: not recorded


@router.post("/quizzes/{quiz_id}/answers", dependencies=[Depends(_need_db)])
async def save_answers(
    quiz_id: str, body: Answers, user: Annotated[str, Depends(current_user)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, Any]:
    async with engine.begin() as conn:
        quiz = (await conn.execute(
            select(quizzes.c.quiz).where(quizzes.c.id == quiz_id, quizzes.c.user_id == user)
        )).scalar()
        if quiz is None:
            raise HTTPException(404, "quiz not found")  # also for other users' quizzes
        items = quiz["items"]
        if len(body.correct) != len(items):
            raise HTTPException(422, "correct must have one entry per quiz item")
        seen = [(i, it["topic"], c) for i, (it, c) in enumerate(zip(items, body.correct, strict=True)) if c is not None]
        await topics.record(conn, user, "quiz", quiz_id, seen)
        await conn.execute(quiz_attempts.insert().values(  # T4: one row per save, for the progress graph
            user_id=user, quiz_id=quiz_id, topic=str(quiz.get("topic") or quiz.get("title") or "Quiz")[:80],
            score=body.score, total=float(sum(c is not None for c in body.correct)),
            marks_per_q=float(quiz.get("marks_per_q") or 1)))
    return {"recorded": len(seen)}
