"""Prep pack (D5): built the first time a student opens a task's pack, then kept.

A reminder or check-in links to /#prep/<task key> (app/reminders.py). Opening it:
1. finds the task (title, deadline) from that student's reminder jobs;
2. searches that student's notes for the task (NR, app/notes.py);
3. asks the quiz engine (Q1) for 5 questions based on those notes;
4. links each question to the notes page that matches it best, as item.source
   "notes:<upload_id>#page=<n>" (None when no page matches);
5. stores it in app.quizzes under the id "prep-<task key>", so reopening never calls the model again.

Numerical answer keys are checked in the browser sandbox when the pack is shown, never here
(AGENTS.md rule 1); this module only builds and stores text.
"""

import asyncio
import re
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app import notes
from app.agent.quiz import Quiz
from app.agent.quiz_gen import ChatJSON, QuizGenerationFailed, generate_quiz
from app.db import quizzes

N_QUESTIONS = 5
RETRY_AFTER_S = 60  # after a failed build: no new model call for this pack for a minute
# frequent words that never make a link on their own (with 4+ letters; shorter words are ignored)
_COMMON = {"what", "which", "when", "where", "does", "with", "from", "that", "this", "into", "than", "then",
           "have", "will", "your", "find", "calculate", "value", "given", "using", "following", "about"}
KEY = re.compile(r"[0-9a-f]{16}")  # app/reminders.py _key(): 16 hex characters
SOURCE = re.compile(r"notes:([a-z]+-[0-9a-f]{32})#page=(\d+)")  # upload ids: "<kind>-<uuid hex>"


class TaskNotFound(Exception):
    """No reminder or check-in of this student links to this pack."""


class ModelNotAvailable(Exception):
    """The pack is not built yet and there is no model to build it."""


class BuildCoolingDown(Exception):
    """The last build of this pack failed less than RETRY_AFTER_S ago."""


async def find_task(engine: AsyncEngine, user_id: str, key: str) -> dict[str, str]:
    sql = text(
        "SELECT payload->>'title' AS title, payload->>'deadline_utc' AS deadline_utc FROM app.jobs "
        "WHERE user_id = :u AND payload->>'prep' = :p ORDER BY id LIMIT 1"
    )
    async with engine.connect() as conn:
        row = (await conn.execute(sql, {"u": user_id, "p": f"/#prep/{key}"})).mappings().first()
    if row is None or not row["title"]:
        raise TaskNotFound(key)
    return {"title": row["title"], "deadline_utc": row["deadline_utc"] or ""}


async def stored(engine: AsyncEngine, user_id: str, key: str) -> Quiz | None:
    q = select(quizzes.c.quiz).where(quizzes.c.id == f"prep-{key}", quizzes.c.user_id == user_id)
    async with engine.connect() as conn:
        raw = (await conn.execute(q)).scalar()
    try:
        return Quiz.model_validate(raw) if raw else None
    except ValidationError:
        return None  # stored by an older schema: rebuilt (and the row replaced) on this open


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", t.lower()) if w not in _COMMON}


async def link(engine: AsyncEngine, user_id: str, quiz: Quiz) -> Quiz:
    """Each question's best-matching page of the student's own notes, or None. A page counts only
    when it shares at least two real words with the question, so one common word ("heat") never
    links a question to an unrelated page."""
    items = []
    for item in quiz.items:
        hits = await notes.search(engine, user_id, item.stem[:300], limit=1)
        good = hits and len(_words(item.stem) & _words(str(hits[0]["text"]))) >= 2
        source = f"notes:{hits[0]['upload_id']}#page={hits[0]['page']}" if good else None
        items.append(item.model_copy(update={"source": source}))
    return quiz.model_copy(update={"items": items})


async def build(engine: AsyncEngine, llm: ChatJSON, user_id: str, key: str, title: str) -> Quiz:
    topic = " ".join(title.split())[:200]  # one line: a title cannot add fields to the prompt
    hits = await notes.search(engine, user_id, topic, limit=5)
    # ask for a few spare: the generator drops duplicates and unusable items
    quiz = await generate_quiz(llm, topic, N_QUESTIONS + 2, notes=[str(h["text"]) for h in hits])
    if len(quiz.items) < N_QUESTIONS:
        raise QuizGenerationFailed(f"only {len(quiz.items)} usable questions")  # nothing stored; 502
    quiz = quiz.model_copy(update={"title": f"Prep pack: {topic}", "items": quiz.items[:N_QUESTIONS]})
    return await link(engine, user_id, quiz)


_locks: dict[str, asyncio.Lock] = {}  # ponytail: per process (Render free runs one)
_failed: dict[str, float] = {}  # key -> monotonic time of the last failed build


async def get_or_build(engine: AsyncEngine, llm: ChatJSON | None, user_id: str, key: str) -> dict[str, Any]:
    """The stored pack, or build and store it. One build at a time per pack (a second tab waits
    for the first), and after a failed build the model is not tried again for RETRY_AFTER_S."""
    task = await find_task(engine, user_id, key)
    slot = f"{user_id}|{key}"
    lock = _locks.setdefault(slot, asyncio.Lock())
    try:
        return await _open(engine, llm, user_id, key, task, slot, lock)
    finally:
        if not lock.locked():
            _locks.pop(slot, None)  # also after a failed build; a stray re-creation is harmless


async def _open(engine: AsyncEngine, llm: ChatJSON | None, user_id: str, key: str,
                task: dict[str, str], slot: str, lock: asyncio.Lock) -> dict[str, Any]:
    async with lock:
        quiz = await stored(engine, user_id, key)
        if quiz is None:
            if llm is None:
                raise ModelNotAvailable(key)
            if time.monotonic() - _failed.get(slot, -RETRY_AFTER_S) < RETRY_AFTER_S:
                raise BuildCoolingDown(key)
            try:
                quiz = await build(engine, llm, user_id, key, task["title"])
            except Exception:
                _failed[slot] = time.monotonic()
                raise
            _failed.pop(slot, None)
            stmt = insert(quizzes).values(id=f"prep-{key}", user_id=user_id, quiz=quiz.model_dump(mode="json"))
            async with engine.begin() as conn:
                await conn.execute(stmt.on_conflict_do_update(
                    index_elements=["id"], set_={"quiz": stmt.excluded.quiz},
                    where=quizzes.c.user_id == user_id))  # another student's row with this id is never touched
            quiz = await stored(engine, user_id, key) or quiz
    return {"task": task, "quiz_id": f"prep-{key}", "quiz": quiz.model_dump(mode="json"),
            "links": [links_of(i.source) for i in quiz.items]}


def links_of(source: str | None) -> dict[str, Any] | None:
    m = SOURCE.fullmatch(source or "")
    return {"upload_id": m[1], "page": int(m[2])} if m else None
