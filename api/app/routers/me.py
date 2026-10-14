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

from app.db import (
    jobs,
    llm_calls,
    note_chunks,
    notices,
    quizzes,
    shared_engine,
    solves,
    topic_results,
)
from app.routers.uploads import get_storage_opt
from app.storage import Storage, StorageError

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
# None when Supabase env is missing: export then lists no files, delete is already 503 without the key
FilesDep = Annotated[Storage | None, Depends(get_storage_opt)]


@router.get("/me/export")
async def export_me(user: UserDep, engine: EngineDep, files: FilesDep) -> JSONResponse:
    out: dict[str, Any] = {"user_id": user, "exported_at": datetime.now(UTC)}
    async with engine.connect() as conn:
        for t in (solves, quizzes, llm_calls, notices, jobs, topic_results, note_chunks):  # heartbeats has no user_id
            rows = (await conn.execute(select(*[c for c in t.c if c.name != "tsv"]).where(t.c.user_id == user))).mappings().all()
            out[t.name] = [dict(r) for r in rows]
    try:  # names and sizes only: the file bytes are not in the JSON
        out["files"] = await files.list(f"{user}/") if files else []
    except StorageError:
        raise HTTPException(502, "could not list your files, try again") from None
    return JSONResponse(
        jsonable_encoder(out),
        headers={"Content-Disposition": 'attachment; filename="studyforge-export.json"'},
    )


@router.delete("/me", status_code=204)
async def delete_me(user: UserDep, engine: EngineDep, http: HttpDep, files: FilesDep) -> Response:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise HTTPException(503, "not available")  # before touching any rows
    async with engine.begin() as conn:
        await conn.execute(solves.delete().where(solves.c.user_id == user))
        await conn.execute(quizzes.delete().where(quizzes.c.user_id == user))
        await conn.execute(notices.delete().where(notices.c.user_id == user))
        await conn.execute(jobs.delete().where(jobs.c.user_id == user))  # reminders, check-ins
        await conn.execute(topic_results.delete().where(topic_results.c.user_id == user))
        await conn.execute(note_chunks.delete().where(note_chunks.c.user_id == user))
        # Anonymise, don't delete: the T7 spend caps sum llm_calls.cost_usd, deleting would
        # let spend accounting drop.
        await conn.execute(update(llm_calls).where(llm_calls.c.user_id == user).values(user_id=None, ip=None))
    # Files go before the auth user. A failure leaves the rows already gone; a retry is idempotent.
    try:
        if files:
            await files.delete_prefix(f"{user}/")
    except StorageError:
        raise HTTPException(502, "data deleted; files could not be removed, try again") from None
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
