"""D5: GET /api/v1/prep/{key} -> {task, quiz_id, quiz, links}. Built when first opened, then kept
(app/prep.py). links[i] is {upload_id, page} for question i, or null when no notes page matches."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine

from app import prep
from app.agent.quiz_gen import ChatJSON, QuizGenerationFailed
from app.llm.errors import BudgetExceeded, LLMError
from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")


def get_llm() -> ChatJSON | None:
    """The model, or None when it is not available (main.py overrides; see wiring.prep_llm).
    A pack that is already stored opens without it."""
    return None


@router.get("/prep/{key}", dependencies=[Depends(_need_db)])
async def prep_pack(key: str, user: Annotated[str, Depends(current_user)],
                    engine: Annotated[AsyncEngine, Depends(get_engine)],
                    llm: Annotated[ChatJSON | None, Depends(get_llm)]) -> dict[str, Any]:
    if not prep.KEY.fullmatch(key):
        raise HTTPException(404, "no such prep pack")
    try:
        task = await prep.find_task(engine, user, key)  # 404 before any model call
    except prep.TaskNotFound:
        raise HTTPException(404, "no such prep pack") from None  # also another student's task
    if await prep.stored(engine, user, key) is None and llm is None:
        raise HTTPException(503, "the model is not available to build this pack yet")
    try:
        return await prep.get_or_build(engine, llm, user, key) | {"task": task}  # type: ignore[arg-type]
    except BudgetExceeded:
        raise HTTPException(429, "today's model budget is used up; the pack can be built tomorrow") from None
    except (QuizGenerationFailed, LLMError):  # no usable questions, model down, bad JSON: nothing stored
        raise HTTPException(502, "could not build this pack, try again") from None
