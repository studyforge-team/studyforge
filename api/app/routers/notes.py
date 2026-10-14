"""NR: POST /api/v1/notes/{upload_id}/index, GET /api/v1/notes/search?q= (own notes only)."""

from typing import Annotated, Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncEngine

from app import notes
from app.routers.checkins import get_engine
from app.routers.dashboard import _need_db
from app.routers.solve import current_user
from app.routers.uploads import fetch_upload, get_storage
from app.storage import Storage, StorageError

router = APIRouter(prefix="/api/v1")
UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]


@router.post("/notes/{upload_id}/index", dependencies=[Depends(_need_db)])
async def index(upload_id: str, user: UserDep, engine: EngineDep,
                storage: Annotated[Storage, Depends(get_storage)]) -> dict[str, int]:
    if not upload_id.startswith("notes-"):
        raise HTTPException(422, "only notes uploads can be indexed")
    try:
        data, ctype = await fetch_upload(storage, user, upload_id)
    except LookupError:
        raise HTTPException(404, "upload not found") from None
    except StorageError:
        raise HTTPException(502, "storage unavailable, try again") from None
    if ctype != "application/pdf":
        raise HTTPException(415, "only PDF notes can be indexed")
    try:
        return {"pages": await notes.index_upload(engine, user, upload_id, data)}
    except pdfium.PdfiumError:
        raise HTTPException(415, "the PDF could not be read") from None


@router.get("/notes/search", dependencies=[Depends(_need_db)])
async def search(user: UserDep, engine: EngineDep,
                 q: Annotated[str, Query(min_length=1, max_length=500)]) -> dict[str, Any]:
    return {"hits": await notes.search(engine, user, q)}
