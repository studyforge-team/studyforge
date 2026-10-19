"""User data export and deletion — GET /api/v1/me/export, DELETE /api/v1/me.

GDPR-friendly: the export returns all per-user rows across every table;
the delete wipes them.  Both are owner-only operations.

T4: ``quiz_attempts`` is included in export and delete.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import (
    push_subscriptions,
    quiz_attempts,
    quizzes,
    solves,
    topic_results,
    uploads,
)
from app.routers.checkins import _need_db, get_engine
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]

# All tables that store per-user data.  Order matters for export readability.
_USER_TABLES = (
    solves,
    quizzes,
    quiz_attempts,
    topic_results,
    uploads,
    push_subscriptions,
)


@router.get("/me/export", dependencies=[Depends(_need_db)])
async def export_my_data(user: UserDep, engine: EngineDep) -> JSONResponse:
    """Export all data for the authenticated user as JSON."""
    export: dict[str, list[dict[str, Any]]] = {}
    async with engine.connect() as conn:
        for table in _USER_TABLES:
            rows = (
                await conn.execute(
                    table.select().where(table.c.user_id == user)
                )
            ).mappings().all()
            export[table.name] = [dict(r) for r in rows]

    return JSONResponse(
        content=json.loads(json.dumps(export, default=str)),
        media_type="application/json",
    )


@router.delete("/me", dependencies=[Depends(_need_db)])
async def delete_my_data(user: UserDep, engine: EngineDep) -> dict[str, str]:
    """Permanently delete all data for the authenticated user."""
    async with engine.begin() as conn:
        for table in reversed(_USER_TABLES):
            await conn.execute(
                table.delete().where(table.c.user_id == user)
            )
    return {"deleted": "ok"}
