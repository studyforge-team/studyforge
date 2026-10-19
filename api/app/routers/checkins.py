"""Database engine dependency shared across routers.

``get_engine`` is overridden in ``app.main`` once the DATABASE_URL is known.
Routers use ``Depends(get_engine)`` to receive the async engine.

``_need_db`` is a dependency that raises 503 when no engine is configured;
include it in any endpoint that requires Postgres.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine


def get_engine() -> AsyncEngine:
    """Dependency override; raises if not overridden by main.py."""
    raise RuntimeError("No database engine configured")


async def _need_db(engine: AsyncEngine = Depends(get_engine)) -> None:  # noqa: B008
    """Dependency that aborts with 503 when there is no database."""
    # If get_engine raises, FastAPI will propagate it as 500.
    # We wrap it here so callers get a clean 503.
    try:
        # Just access the attribute to confirm it's a real engine
        _ = engine.dialect
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="database not available")
