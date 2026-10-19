"""Uploads router — POST /api/v1/uploads and POST /api/v1/uploads/{id}/read.

Files are stored in Supabase Storage under ``{user_id}/{upload_id}``.
The router never returns raw file bytes; it returns the upload id so other
routes can reference the file.

Pattern used by T1 to fetch upload bytes:
    from app.routers.uploads import fetch_upload, get_storage
    data, mime = await fetch_upload(storage, user, upload_id)  # LookupError -> 404
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncEngine

from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user

router = APIRouter(prefix="/api/v1")

ID_RE = re.compile(r"^[0-9a-f]{32}$")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Storage dependency ────────────────────────────────────────────────────────


class _Storage:
    """Thin wrapper; the real implementation talks to Supabase Storage."""

    async def upload(self, key: str, data: bytes, mime: str) -> None:
        """Store *data* at *key*."""

    async def download(self, key: str) -> tuple[bytes, str]:
        """Return ``(data, mime)``; raise ``LookupError`` if not found."""
        raise LookupError(key)


def get_storage() -> _Storage:
    """Dependency override set in ``main.py`` once Supabase is configured."""
    return _Storage()


StorageDep = Annotated[_Storage, Depends(get_storage)]
UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]


# ── helpers ───────────────────────────────────────────────────────────────────


async def fetch_upload(
    storage: _Storage,
    user_id: str,
    upload_id: str,
) -> tuple[bytes, str]:
    """Download the file for *upload_id* owned by *user_id*.

    Raises ``LookupError`` if not found or not owned by the user.
    The caller should convert ``LookupError`` to an HTTP 404.
    """
    if not ID_RE.match(upload_id):
        raise LookupError(upload_id)
    key = f"{user_id}/{upload_id}"
    return await storage.download(key)


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.post("/uploads", dependencies=[Depends(_need_db)])
async def upload_file(
    file: UploadFile,
    user: UserDep,
    storage: StorageDep,
) -> dict[str, str]:
    """Accept a file, store it in Supabase Storage, return the upload id."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    upload_id = uuid.uuid4().hex
    mime = file.content_type or "application/octet-stream"
    key = f"{user}/{upload_id}"
    await storage.upload(key, data, mime)
    return {"upload_id": upload_id}


@router.post("/uploads/{upload_id}/read", dependencies=[Depends(_need_db)])
async def read_upload(
    upload_id: str,
    user: UserDep,
    storage: StorageDep,
) -> dict[str, Any]:
    """Read text / LaTeX from an uploaded file via the vision reader."""
    try:
        _data, _mime = await fetch_upload(storage, user, upload_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="upload not found")

    # Stub: the real implementation calls read_question.
    return {"text": "", "latex": "", "confidence": "low"}
