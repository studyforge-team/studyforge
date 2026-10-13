"""D7: POST /api/v1/checkins/{job_id} {"correct": bool}. The browser asks the quiz question
and reports the outcome; the server only records it (see app/reminders.py)."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app.reminders import answer_checkin
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")


def get_engine() -> AsyncEngine:
    raise RuntimeError("app must override get_engine")


def now() -> datetime:  # a dependency so tests can drive a fake clock
    return datetime.now(UTC)


class Answer(BaseModel):
    correct: bool


@router.post("/checkins/{job_id}")
async def answer(
    job_id: int, body: Answer, user: Annotated[str, Depends(current_user)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    at: Annotated[datetime, Depends(now)],
) -> dict[str, Any]:
    try:
        out = await answer_checkin(engine, user, job_id, body.correct, at)
    except ValueError as err:
        raise HTTPException(status_code=409, detail="check-in not answerable") from err
    if out is None:
        raise HTTPException(status_code=404, detail="check-in not found")  # also for other users' jobs
    return out
