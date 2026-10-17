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
from app.routers.solve import current_user, spend_context

router = APIRouter(prefix="/api/v1")


def get_llm() -> ChatJSON | None:
    """The model, or None when it is not available (main.py overrides; see wiring.prep_llm).
    A pack that is already stored opens without it."""
    return None


@router.get("/prep/{key}", dependencies=[Depends(_need_db), Depends(spend_context)])  # caps + cost rows per student
async def prep_pack(key: str, user: Annotated[str, Depends(current_user)],
                    engine: Annotated[AsyncEngine, Depends(get_engine)],
                    llm: Annotated[ChatJSON | None, Depends(get_llm)]) -> dict[str, Any]:
    if not prep.KEY.fullmatch(key):
        raise HTTPException(404, "no such prep pack")
    try:
        await prep.find_task(engine, user, key)  # 404 before any model call
    except prep.TaskNotFound:
        raise HTTPException(404, "no such prep pack") from None  # also another student's task
    try:
        return await prep.get_or_build(engine, llm, user, key)
    except prep.ModelNotAvailable:
        raise HTTPException(503, "the model is not available to build this pack yet") from None
    except prep.BuildCoolingDown:
        raise HTTPException(503, "building this pack failed a moment ago; try again in a minute") from None
    except BudgetExceeded:
        raise HTTPException(429, "today's model budget is used up; the pack can be built tomorrow") from None
    except (QuizGenerationFailed, LLMError):  # too few usable questions, model down, bad JSON: nothing stored
        raise HTTPException(502, "could not build this pack, try again") from None
