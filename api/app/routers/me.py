"""Privacy panel (D10): export my data, delete my account."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import llm_calls, notices, quizzes, shared_engine, solves

router = APIRouter(prefix="/api/v1")


def current_user() -> str:  # main.py overrides with auth.current_user (same pattern as solve.py)
    raise HTTPException(status_code=401, detail="not signed in")


def get_engine() -> AsyncEngine:
    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(503, "not available")
    return shared_engine()


async def get_http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10) as client:
        yield client


UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http)]


@router.get("/me/export")
async def export_me(user: UserDep, engine: EngineDep) -> JSONResponse:
    out: dict[str, Any] = {"user_id": user, "exported_at": datetime.now(UTC)}
    async with engine.connect() as conn:
        for t in (solves, quizzes, llm_calls, notices):  # heartbeats has no user_id
            rows = (await conn.execute(select(t).where(t.c.user_id == user))).mappings().all()
            out[t.name] = [dict(r) for r in rows]
    return JSONResponse(
        jsonable_encoder(out),
        headers={"Content-Disposition": 'attachment; filename="studyforge-export.json"'},
    )


@router.delete("/me", status_code=204)
async def delete_me(user: UserDep, engine: EngineDep, http: HttpDep) -> Response:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise HTTPException(503, "not available")  # before touching any rows
    async with engine.begin() as conn:
        await conn.execute(solves.delete().where(solves.c.user_id == user))
        await conn.execute(quizzes.delete().where(quizzes.c.user_id == user))
        await conn.execute(notices.delete().where(notices.c.user_id == user))
        # Anonymise, don't delete: the T7 spend caps sum llm_calls.cost_usd, deleting would
        # let spend accounting drop.
        await conn.execute(update(llm_calls).where(llm_calls.c.user_id == user).values(user_id=None, ip=None))
    # Storage files: no upload storage exists yet; delete the user's bucket objects here when it does.
    gone = False
    try:
        r = await http.delete(
            os.environ["SUPABASE_URL"].rstrip("/") + f"/auth/v1/admin/users/{user}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        gone = r.is_success or r.status_code == 404  # 404 = already removed (retry)
    except httpx.HTTPError:
        pass  # never log: the exception text can carry request headers
    if not gone:
        raise HTTPException(502, "data deleted; sign-in account could not be removed, try again")
    return Response(status_code=204)
