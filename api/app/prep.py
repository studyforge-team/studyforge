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

import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app import notes
from app.agent.quiz import Quiz
from app.agent.quiz_gen import ChatJSON, generate_quiz
from app.db import quizzes

N_QUESTIONS = 5
KEY = re.compile(r"[0-9a-f]{16}")  # app/reminders.py _key(): 16 hex characters
SOURCE = re.compile(r"notes:([a-z]+-[0-9a-f]{32})#page=(\d+)")  # upload ids: "<kind>-<uuid hex>"


class TaskNotFound(Exception):
    """No reminder or check-in of this student links to this pack."""


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
    return Quiz.model_validate(raw) if raw else None


async def link(engine: AsyncEngine, user_id: str, quiz: Quiz) -> Quiz:
    """Each question's best-matching page of the student's own notes, or None."""
    items = []
    for item in quiz.items:
        hits = await notes.search(engine, user_id, item.stem[:300], limit=1)
        source = f"notes:{hits[0]['upload_id']}#page={hits[0]['page']}" if hits else None
        items.append(item.model_copy(update={"source": source}))
    return quiz.model_copy(update={"items": items})


async def build(engine: AsyncEngine, llm: ChatJSON, user_id: str, key: str, title: str) -> Quiz:
    hits = await notes.search(engine, user_id, title, limit=5)
    quiz = await generate_quiz(llm, title, N_QUESTIONS, notes=[str(h["text"]) for h in hits])
    return await link(engine, user_id, quiz.model_copy(update={"title": f"Prep pack: {title}"}))


async def get_or_build(engine: AsyncEngine, llm: ChatJSON, user_id: str, key: str) -> dict[str, Any]:
    task = await find_task(engine, user_id, key)
    quiz = await stored(engine, user_id, key)
    if quiz is None:
        quiz = await build(engine, llm, user_id, key, task["title"])
        stmt = insert(quizzes).values(id=f"prep-{key}", user_id=user_id, quiz=quiz.model_dump(mode="json"))
        async with engine.begin() as conn:  # two tabs opening at once: the first one stored wins
            await conn.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))
        quiz = await stored(engine, user_id, key) or quiz
    return {"task": task, "quiz_id": f"prep-{key}", "quiz": quiz.model_dump(mode="json"),
            "links": [links_of(i.source) for i in quiz.items]}


def links_of(source: str | None) -> dict[str, Any] | None:
    m = SOURCE.fullmatch(source or "")
    return {"upload_id": m[1], "page": int(m[2])} if m else None
