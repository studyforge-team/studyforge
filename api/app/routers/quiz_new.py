"""T1: POST /api/v1/quizzes — generate a quiz on a topic or uploaded material.

New file, new router; registered in ``app/main.py`` with one
``app.include_router(quiz_new.router)`` line.

Rules (AGENTS.md / prompt):
- No new dependencies.
- Additive only: existing callers of generate_quiz are unaffected.
- No secrets; no model code runs on the server.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agent.quiz_gen import ChatJSON, QuizGenerationFailed, generate_quiz
from app.agent.read_question import read_question
from app.db import quizzes
from app.llm.errors import BudgetExceeded, LLMError
from app.notes import pdf_pages
from app.pdfium_lock import one_at_a_time
from app.routers.checkins import _need_db, get_engine
from app.routers.prep import get_llm
from app.routers.solve import current_user, spend_context
from app.routers.uploads import _Storage, fetch_upload, get_storage

router = APIRouter(prefix="/api/v1")

UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
LLMDep = Annotated[ChatJSON | None, Depends(get_llm)]
StorageDep = Annotated[_Storage, Depends(get_storage)]

_PDF_PAGE_LIMIT = 10
_PDF_CHAR_LIMIT = 12_000
_VISION_FALLBACK_THRESHOLD = 200
_MAX_VISION_PAGES = 3


class QuizRequest(BaseModel):
    model_config = {"extra": "forbid"}

    topic: str = Field(min_length=1, max_length=80)
    n_items: int = Field(default=5, ge=3, le=20)
    kinds: Literal["mcq", "blank", "mixed"] = "mcq"
    marks_per_q: Literal[1, 2, 4] = 1
    upload_id: str | None = None


@router.post(
    "/quizzes",
    dependencies=[Depends(_need_db), Depends(spend_context)],
)
async def create_quiz(
    body: QuizRequest,
    user: UserDep,
    engine: EngineDep,
    llm: LLMDep,
    storage: StorageDep,
) -> dict[str, Any]:
    """Generate a quiz for *topic*, optionally grounded in uploaded material."""

    # ── 503 when no model is configured ──────────────────────────────────────
    if llm is None:
        raise HTTPException(status_code=503, detail="quiz not available")

    # ── Resolve upload material ───────────────────────────────────────────────
    notes: list[str] = []
    if body.upload_id is not None:
        try:
            data, mime = await fetch_upload(storage, user, body.upload_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="upload not found")

        if mime == "application/pdf":
            pages = await one_at_a_time(pdf_pages(data))
            text_content = "\n".join(
                t for _, t in pages[:_PDF_PAGE_LIMIT] if t.strip()
            )[:_PDF_CHAR_LIMIT]

            if len(text_content) < _VISION_FALLBACK_THRESHOLD:
                # Scanned/handwritten PDF — fall back to vision
                texts: list[str] = []
                for page_no in range(1, min(len(pages) + 1, _MAX_VISION_PAGES + 1)):
                    try:
                        result = await read_question(
                            llm, data, mime, page=page_no  # type: ignore[arg-type]
                        )
                        texts.append(result.text or "")
                    except Exception:  # noqa: BLE001, S110
                        pass
                text_content = "\n".join(texts)

            if text_content.strip():
                notes = [text_content]
        else:
            # Image: use vision reader directly
            texts = []
            for page_no in range(1, _MAX_VISION_PAGES + 1):
                try:
                    result = await read_question(
                        llm, data, mime, page=page_no  # type: ignore[arg-type]
                    )
                    texts.append(result.text or "")
                except Exception:  # noqa: BLE001
                    break
            notes = ["\n".join(texts)] if any(texts) else []

    # ── Generate quiz ─────────────────────────────────────────────────────────
    try:
        quiz = await generate_quiz(
            llm,
            body.topic,
            body.n_items,
            notes=notes,
            kinds=body.kinds,  # type: ignore[call-arg]
        )
    except BudgetExceeded:
        raise HTTPException(status_code=429, detail="daily budget exceeded")
    except (QuizGenerationFailed, LLMError):
        raise HTTPException(
            status_code=502, detail="could not build this quiz, try again"
        )

    # ── Store quiz with extra metadata ────────────────────────────────────────
    quiz_id = uuid.uuid4().hex
    quiz_data = {
        **quiz.model_dump(mode="json"),
        "topic": body.topic,
        "marks_per_q": body.marks_per_q,
    }
    async with engine.begin() as conn:
        await conn.execute(
            quizzes.insert().values(
                id=quiz_id,
                user_id=user,
                quiz=quiz_data,
            )
        )

    n = len(quiz.items)
    suggested_minutes = n * (2 if body.kinds == "mcq" else 3)

    return {
        "id": quiz_id,
        "title": quiz.title,
        "items": [i.model_dump(mode="json") for i in quiz.items],
        "topic": body.topic,
        "marks_per_q": body.marks_per_q,
        "total_marks": n * body.marks_per_q,
        "suggested_minutes": suggested_minutes,
    }
