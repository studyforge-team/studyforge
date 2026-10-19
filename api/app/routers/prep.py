"""Prep pack router — builds and stores a quiz from the student's notes.

Pattern used by T1 for getting the model client:
    from app.routers.prep import get_llm
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.agent.quiz_gen import ChatJSON, QuizGenerationFailed, generate_quiz
from app.llm.errors import BudgetExceeded, LLMError
from app.routers.checkins import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

UserDep = Annotated[str, Depends(current_user)]


def get_llm() -> ChatJSON | None:
    """Dependency override set in ``main.py`` once a model is configured.

    Returns ``None`` when no model client is available.
    """
    return None


LLMDep = Annotated[ChatJSON | None, Depends(get_llm)]


@router.post("/prep/{topic}", dependencies=[Depends(_need_db)])
async def make_prep_pack(
    topic: str,
    user: UserDep,
    llm: LLMDep,
) -> dict[str, Any]:
    """Generate a prep pack quiz for *topic* using the student's notes."""
    if llm is None:
        raise HTTPException(status_code=503, detail="quiz not available")
    try:
        quiz = await generate_quiz(llm, topic, 5, notes=())
    except BudgetExceeded:
        raise HTTPException(status_code=429, detail="daily budget exceeded")
    except (QuizGenerationFailed, LLMError):
        raise HTTPException(status_code=502, detail="could not build this quiz, try again")

    return {"title": quiz.title, "items": [i.model_dump(mode="json") for i in quiz.items]}
