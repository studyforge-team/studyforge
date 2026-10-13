import asyncio

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import db_url, metadata


def _run(conn):  # type: ignore[no-untyped-def]
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))  # version table needs it first
    context.configure(
        connection=conn, target_metadata=metadata,
        version_table_schema="app", include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    engine = create_async_engine(db_url())
    async with engine.begin() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


# ponytail: online mode only — no offline SQL generation
asyncio.run(main())
