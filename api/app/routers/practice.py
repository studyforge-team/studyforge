"""FO1: POST /api/v1/practice-attempts. Saves a self-marked practice result (company OA) into
app.quiz_attempts, so it shows in GET /api/v1/quiz-attempts (My progress) like a quiz."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import quiz_attempts
from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")


class Practice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=80)
    score: float = Field(ge=0)
    total: int = Field(ge=1, le=50)
    marks_per_q: Literal[1, 2, 4] = 1


@router.post("/practice-attempts", dependencies=[Depends(_need_db)])
async def save_practice(
    body: Practice, user: Annotated[str, Depends(current_user)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, bool]:
    async with engine.begin() as conn:
        await conn.execute(quiz_attempts.insert().values(
            user_id=user, quiz_id="practice:" + body.topic, topic=body.topic,
            score=min(body.score, float(body.total)), total=float(body.total),
            marks_per_q=float(body.marks_per_q)))
    return {"ok": True}
