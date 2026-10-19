"""FastAPI application factory.

Registers all routers and overrides the dependency stubs with real
implementations when environment variables are present.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.routers.checkins as checkins_mod
import app.routers.dashboard as dashboard_mod
import app.routers.me as me_mod
import app.routers.prep as prep_mod
import app.routers.progress as progress_mod
import app.routers.quiz_new as quiz_new_mod
import app.routers.quizzes as quizzes_mod
import app.routers.solve as solve_mod
import app.routers.uploads as uploads_mod

app = FastAPI(title="StudyForge API", version="0.9.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(solve_mod.router)
app.include_router(dashboard_mod.router)
app.include_router(quizzes_mod.router)
app.include_router(quiz_new_mod.router)
app.include_router(uploads_mod.router)
app.include_router(progress_mod.router)
app.include_router(me_mod.router)
app.include_router(prep_mod.router)

# ── Dependency overrides when DATABASE_URL is set ─────────────────────────────
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    from sqlalchemy.ext.asyncio import create_async_engine

    _engine = create_async_engine(_db_url, pool_pre_ping=True)

    def _get_engine():  # type: ignore[no-untyped-def]
        return _engine

    app.dependency_overrides[checkins_mod.get_engine] = _get_engine

# ── Auth override ─────────────────────────────────────────────────────────────
if not os.getenv("SUPABASE_URL"):
    # Development mode: every request is the same dev user
    app.dependency_overrides[solve_mod.current_user] = solve_mod.dev_user


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
