"""Postgres (Supabase session pooler) tables in schema `app` + the store implementations."""

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import asdict
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Double,
    Identity,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app import spend
from app.agent.quiz import Quiz
from app.agent.state import SolveState, norm
from app.llm.cost import CallRecord

metadata = MetaData(schema="app")
_now = func.now()

solves = Table(
    "solves", metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False, index=True),
    Column("state", JSONB, nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=_now),
)
quizzes = Table(
    "quizzes", metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, nullable=False, index=True),
    Column("quiz", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=_now),
)
llm_calls = Table(
    "llm_calls", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("solve_id", Text),
    Column("role", Text, nullable=False),
    Column("model_id", Text, nullable=False),
    Column("ok", Boolean, nullable=False),
    Column("error", Text),
    Column("prompt_tokens", Integer, nullable=False),
    Column("completion_tokens", Integer, nullable=False),
    Column("cost_usd", Double),  # NULL while the model has no price in the registry
    Column("latency_ms", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=_now, index=True),
    Column("user_id", Text),  # T7: who made the call
    Column("ip", Text),
)
heartbeats = Table(
    "heartbeats", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("at", DateTime(timezone=True), nullable=False, server_default=_now),
    Column("source", Text, nullable=False),
)
jobs = Table(
    "jobs", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("user_id", Text, nullable=False, index=True),
    Column("kind", Text, nullable=False),
    Column("dedupe_key", Text, nullable=False, unique=True),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("sent_at", DateTime(timezone=True)),
    Column("payload", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
)


def db_url() -> str:
    url = os.environ["DATABASE_URL"]
    for plain in ("postgresql://", "postgres://"):
        if url.startswith(plain):
            return "postgresql+asyncpg://" + url[len(plain):]
    return url


def make_engine() -> AsyncEngine:
    # Session pooler (port 5432) keeps prepared statements working; only the transaction
    # pooler (6543) would need connect_args={"statement_cache_size": 0}.
    # pre_ping: Render sleeps and the pooler drops idle connections
    return create_async_engine(db_url(), pool_pre_ping=True)


class PgStateStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._conn: ContextVar[AsyncConnection | None] = ContextVar("conn", default=None)

    @asynccontextmanager
    async def lock(self, solve_id: str) -> AsyncIterator[None]:
        # advisory lock, not SELECT FOR UPDATE: works before the row exists
        async with self._engine.begin() as conn:
            await conn.execute(text("select pg_advisory_xact_lock(hashtext(:i))"), {"i": solve_id})
            token = self._conn.set(conn)
            try:
                yield
            finally:
                self._conn.reset(token)

    @asynccontextmanager
    async def _use(self) -> AsyncIterator[AsyncConnection]:
        held = self._conn.get()
        if held is not None:
            yield held
        else:
            async with self._engine.begin() as conn:
                yield conn

    async def get(self, solve_id: str) -> SolveState | None:
        async with self._use() as conn:
            row = (await conn.execute(solves.select().where(solves.c.id == solve_id))).first()
        return SolveState.model_validate(row.state) if row else None

    async def cached(self, question: str) -> dict[str, Any] | None:
        # ponytail: unindexed scan of solves — add an expression index on the normalised
        # question if the table grows past a few thousand rows
        sql = text(
            "select state->'last_step' from app.solves "
            "where state->>'status'='done' and state->'last_step' is not null "
            "and not (state->'flags' ?| array['limit_reached','cached','spend_cap']) "
            "and lower(btrim(regexp_replace(state->>'question', '\\s+', ' ', 'g'))) = :q "
            "order by updated_at desc limit 1"
        )
        async with self._use() as conn:
            return (await conn.execute(sql, {"q": norm(question)})).scalar()

    async def save(self, state: SolveState) -> None:
        values: dict[str, Any] = {
            "id": state.id, "user_id": state.user_id, "state": state.model_dump(mode="json"),
        }
        stmt = insert(solves).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"], set_={"state": stmt.excluded.state, "updated_at": _now}
        )
        async with self._use() as conn:
            await conn.execute(stmt)


class PgQuizStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, user_id: str, quiz: Quiz) -> str:
        quiz_id = uuid.uuid4().hex
        async with self._engine.begin() as conn:
            await conn.execute(
                quizzes.insert().values(id=quiz_id, user_id=user_id, quiz=quiz.model_dump(mode="json"))
            )
        return quiz_id


class PgCostRecorder:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(self, row: CallRecord) -> None:
        w = spend.who.get()
        values = asdict(row) | {"user_id": w.user_id, "ip": w.ip}
        async with self._engine.begin() as conn:
            await conn.execute(llm_calls.insert().values(**values))


async def beat(engine: AsyncEngine, source: str) -> bool:
    """Keep-alive: insert a heartbeat unless one is under 60 s old (a public endpoint must not
    be able to spam the table). Returns whether a row was written; also serves as the SELECT."""
    stmt = text(
        "insert into app.heartbeats (source) select :s "
        "where not exists (select 1 from app.heartbeats where at > now() - interval '60 seconds')"
    )
    async with engine.begin() as conn:
        return (await conn.execute(stmt, {"s": source})).rowcount == 1
