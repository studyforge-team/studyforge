"""Database metadata, table objects and store implementations.

This module declares the SQLAlchemy Core metadata for all tables in the
``app`` schema.  It also provides ``PgQuizStore`` and related helpers.

Only tables owned by this service are declared here.  Supabase Auth tables
(``auth.users``, etc.) are never touched directly.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Float,
    Index,
    MetaData,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agent.quiz import Quiz

metadata = MetaData(schema="app")

# ── solves ────────────────────────────────────────────────────────────────────
solves = Table(
    "solves",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("state", JSONB, nullable=False),
    Column("updated_at", TIMESTAMPTZ, server_default=text("now()")),
)

# ── quizzes ───────────────────────────────────────────────────────────────────
quizzes = Table(
    "quizzes",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("quiz", JSONB, nullable=False),
    Column("created_at", TIMESTAMPTZ, server_default=text("now()")),
)

# ── topic_results ─────────────────────────────────────────────────────────────
topic_results = Table(
    "topic_results",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", Text, nullable=False),
    Column("topic", Text, nullable=False),
    Column("correct", Boolean, nullable=False),
    Column("created_at", TIMESTAMPTZ, server_default=text("now()")),
)

# ── quiz_attempts (T4) ────────────────────────────────────────────────────────
quiz_attempts = Table(
    "quiz_attempts",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", Text, nullable=False),
    Column("quiz_id", Text, nullable=False),
    Column("topic", Text, nullable=False),
    Column("score", Float, nullable=False),
    Column("total", Float, nullable=False),
    Column("marks_per_q", Float, nullable=False, server_default=text("1")),
    Column("created_at", TIMESTAMPTZ, server_default=text("now()")),
    Index("ix_quiz_attempts_user_topic", "user_id", "topic", "created_at"),
)

# ── uploads (reference; actual storage is Supabase) ───────────────────────────
uploads = Table(
    "uploads",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("mime", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, server_default=text("now()")),
)

# ── push_subscriptions ────────────────────────────────────────────────────────
push_subscriptions = Table(
    "push_subscriptions",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", Text, nullable=False),
    Column("endpoint", Text, nullable=False),
    Column("p256dh", Text, nullable=False),
    Column("auth", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, server_default=text("now()")),
)


class PgQuizStore:
    """PostgreSQL-backed quiz store (implements ``QuizStore`` protocol)."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, user_id: str, quiz: Quiz) -> str:
        quiz_id = uuid.uuid4().hex
        async with self._engine.begin() as conn:
            await conn.execute(
                quizzes.insert().values(
                    id=quiz_id,
                    user_id=user_id,
                    quiz=quiz.model_dump(mode="json"),
                )
            )
        return quiz_id

    async def load(self, quiz_id: str, user_id: str) -> dict[str, Any] | None:
        """Load a quiz row; returns ``None`` if not found or wrong owner."""
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    quizzes.select().where(
                        quizzes.c.id == quiz_id,
                        quizzes.c.user_id == user_id,
                    )
                )
            ).fetchone()
        return dict(row._mapping) if row else None  # type: ignore[union-attr]
