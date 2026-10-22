"""T1: POST /api/v1/quizzes -> a quiz on a topic, optionally grounded in the student's own upload.

The quiz is stored like a prep pack's (app.quizzes) plus `topic` and `marks_per_q`, so
POST /quizzes/{id}/answers (which reads only quiz["items"]) accepts it unchanged.
"""

import asyncio
import time
import uuid
from typing import Annotated, Any, Literal

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agent.quiz_gen import (
    ChatJSON,
    QuizGenerationFailed,
    _normalise,
    generate_quiz,
)
from app.agent.read_question import UnsupportedUpload, read_question
from app.db import quizzes
from app.llm.errors import BudgetExceeded, LLMError
from app.notes import pdf_pages
from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.prep import get_llm
from app.routers.solve import current_user, spend_context
from app.routers.uploads import fetch_upload, get_storage_opt
from app.storage import Storage, StorageError

router = APIRouter(prefix="/api/v1")

PDF_PAGES = 10  # text layer: first pages only
PDF_CHARS = 12_000
MIN_TEXT = 200  # less text than this: a scan or handwriting, read it with the vision model
VISION_PAGES = 3
MAX_BATCHES = 8
FOCUSES = ("definitions and laws", "design choices and trade-offs", "common mistakes and limiting cases",
           "applications and reasoning")
SOLVE_CHARS = 4000  # the /solve question limit


class QuizRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=80)
    n_items: int = Field(default=5, ge=3, le=20)
    kinds: Literal["mcq", "blank", "mixed"] = "mcq"
    marks_per_q: Literal[1, 2, 4] = 1
    upload_id: str | None = None


def _text_layer(data: bytes) -> str:
    try:
        pages = pdf_pages(data)  # takes the pdfium lock itself
    except pdfium.PdfiumError:
        return ""
    return "\n".join(t for n, t in pages if n <= PDF_PAGES)[:PDF_CHARS]


async def _material(llm: ChatJSON, data: bytes, mime: str) -> str:
    """Text of the upload: the PDF text layer, else the vision model on up to 3 pages."""
    if mime == "application/pdf":
        text = await asyncio.to_thread(_text_layer, data)
        if len(text) >= MIN_TEXT:
            return text
        pages = range(1, VISION_PAGES + 1)
    else:
        text, pages = "", range(1, 2)  # one image
    if not hasattr(llm, "vision"):  # a model client without a vision role: keep what the text layer gave
        return text
    parts = [text] if text else []
    for page in pages:
        try:
            parts.append((await read_question(llm, data, mime, page)).text)  # type: ignore[arg-type]
        except UnsupportedUpload:
            break  # past the last page, or not readable as an image
        except BudgetExceeded:
            raise
        except LLMError:
            continue
    return "\n\n".join(p for p in parts if p.strip())[:PDF_CHARS]


@router.post("/quizzes", dependencies=[Depends(_need_db), Depends(spend_context)])
async def create_quiz(
    body: QuizRequest, user: Annotated[str, Depends(current_user)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    llm: Annotated[ChatJSON | None, Depends(get_llm)],
    storage: Annotated[Storage | None, Depends(get_storage_opt)],
) -> dict[str, Any]:
    if llm is None:
        raise HTTPException(503, "quiz not available")
    data, mime = b"", ""
    if body.upload_id is not None:
        if storage is None:
            raise HTTPException(503, "quiz not available")
        try:
            data, mime = await fetch_upload(storage, user, body.upload_id)
        except LookupError:
            raise HTTPException(404, "no such upload") from None
        except StorageError:
            raise HTTPException(502, "storage unavailable, try again") from None
    try:
        notes: list[str] = []
        if body.upload_id is not None:
            text = await _material(llm, data, mime)
            if not text.strip():
                raise HTTPException(422, "could not read any text from this upload")
            notes = [text]
        title = ""
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        # batches of 2 run at once (about 6 s each); ask n + n/5 over all batches to survive drops and dupes
        total = body.n_items + -(-body.n_items // 5)
        count = min(MAX_BATCHES, -(-total // 2))
        sizes = [total // count + (k < total % count) for k in range(count)]
        deadline = time.monotonic() + 80  # the browser gives up after 90 s
        results = await asyncio.gather(
            *(generate_quiz(llm, body.topic, size, notes=notes, kinds=body.kinds, focus=FOCUSES[k % 4],
                            min_items=1, deadline=deadline) for k, size in enumerate(sizes)),
            return_exceptions=True)
        failed: BaseException | None = None
        for res in results:
            if isinstance(res, BaseException):
                if not isinstance(res, (QuizGenerationFailed, LLMError)):
                    raise res
                failed = failed or res  # a failed batch: keep what the others gave
                continue
            title = title or res.title
            for it in res.model_dump(mode="json")["items"]:
                key = _normalise(it["stem"])
                if key not in seen:
                    seen.add(key)
                    items.append(it)
        if not items:
            raise failed or QuizGenerationFailed("no usable questions")
        items = items[: body.n_items]
    except BudgetExceeded:
        raise HTTPException(429, "today's model budget is used up; try again tomorrow") from None
    except (QuizGenerationFailed, LLMError):
        raise HTTPException(502, "could not build this quiz, try again") from None
    quiz_id = uuid.uuid4().hex
    async with engine.begin() as conn:
        await conn.execute(quizzes.insert().values(
            id=quiz_id, user_id=user,
            quiz={"title": title, "items": items, "topic": body.topic, "marks_per_q": body.marks_per_q}))
    n = len(items)
    return {"id": quiz_id, "title": title, "items": items, "topic": body.topic,
            "marks_per_q": body.marks_per_q, "total_marks": n * body.marks_per_q,
            "suggested_minutes": n * (2 if body.kinds == "mcq" else 3)}


def _page_one(data: bytes) -> str:
    try:
        return next((t for n, t in pdf_pages(data) if n == 1), "")
    except pdfium.PdfiumError:
        return ""


def _trim(text: str) -> str:
    cut = text[:SOLVE_CHARS]
    if len(text) > SOLVE_CHARS and "\n" in cut:
        cut = cut[: cut.rindex("\n")]
    return cut


@router.post("/uploads/{upload_id}/read", dependencies=[Depends(spend_context)])
async def read_upload(
    upload_id: str, user: Annotated[str, Depends(current_user)],
    llm: Annotated[ChatJSON | None, Depends(get_llm)],
    storage: Annotated[Storage | None, Depends(get_storage_opt)],
) -> dict[str, str]:
    """Question text from page 1 of an upload, for the Solve confirm screen. Never solves."""
    if llm is None or storage is None or not hasattr(llm, "vision"):
        raise HTTPException(503, "reading not available")
    try:
        data, mime = await fetch_upload(storage, user, upload_id)
    except LookupError:
        raise HTTPException(404, "no such upload") from None
    except StorageError:
        raise HTTPException(502, "storage unavailable, try again") from None
    empty = {"text": "", "latex": "", "figure_description": "", "confidence": "low"}
    try:
        if mime == "application/pdf":
            text = await asyncio.to_thread(_page_one, data)
            if len(text) >= MIN_TEXT:  # no model call; a text layer can mangle maths, so "medium"
                return {**empty, "text": _trim(text), "confidence": "medium"}
        q = await read_question(llm, data, mime, 1)  # type: ignore[arg-type]
    except UnsupportedUpload:
        return empty
    except BudgetExceeded:
        raise HTTPException(429, "today's model budget is used up; try again tomorrow") from None
    except LLMError:
        raise HTTPException(502, "could not read this file, try again") from None
    parts = [q.text]
    if q.latex and q.latex not in q.text:
        parts.append(f"$$\n{q.latex}\n$$")
    if q.figure_description:
        parts.append(f"Figure: {q.figure_description}")
    return {**q.model_dump(), "text": _trim("\n\n".join(x.strip() for x in parts if x.strip()))}
