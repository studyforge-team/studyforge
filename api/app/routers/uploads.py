"""Uploads (C1): a student's photo of a question or a notes PDF -> private Supabase Storage bucket.

POST /api/v1/uploads (multipart: file, kind=question|notes) -> {"upload_id"}
GET  /api/v1/uploads/{upload_id} -> {"url"}  signed, valid 10 minutes

The object path is "<user_id>/<upload_id>", always built from the signed-in user, so another
user's id is simply not found. The client's content type and file name are ignored: the type is
sniffed from magic bytes, and SVG/HTML never match.
"""

import os
import re
import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Literal

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.routing import APIRoute

from app.storage import Storage, StorageError, SupabaseStorage

MAX_BYTES = 10 * 1024 * 1024
MAX_FILES = 20  # per user: abuse cap on the free storage tier
SIGN_S = 600
ID_RE = re.compile(r"(question|notes)-[0-9a-f]{32}")



class _SizeGuardRoute(APIRoute):
    """FastAPI parses the multipart form before the handler runs, so a declared oversize body
    must be refused here, before any of it is read."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        inner = super().get_route_handler()

        async def handler(request: Request) -> Response:
            declared = request.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_BYTES + 512 * 1024:  # + multipart overhead
                raise HTTPException(413, "file too large (10 MB max)")
            return await inner(request)
        return handler


router = APIRouter(prefix="/api/v1", route_class=_SizeGuardRoute)
_http: httpx.AsyncClient | None = None


def current_user() -> str:  # main.py overrides with auth.current_user (same pattern as solve.py)
    raise HTTPException(status_code=401, detail="not signed in")


def get_storage_opt() -> Storage | None:
    """None when Supabase env is missing (the privacy export/delete then skip files)."""
    global _http
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    _http = _http or httpx.AsyncClient(timeout=30)
    return SupabaseStorage(_http, url, key, os.environ.get("STORAGE_BUCKET", "uploads"))


def get_storage() -> Storage:
    s = get_storage_opt()
    if s is None:
        raise HTTPException(503, "not available")
    return s


UserDep = Annotated[str, Depends(current_user)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def sniff(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


async def fetch_upload(storage: Storage, user_id: str, upload_id: str) -> tuple[bytes, str]:
    """(bytes, content_type) of the user's own upload. LookupError if none (incl. a bad id)."""
    if not ID_RE.fullmatch(upload_id):
        raise LookupError(upload_id)
    return await storage.get(f"{user_id}/{upload_id}")


@router.post("/uploads")
async def upload(
    user: UserDep, storage: StorageDep,
    file: Annotated[UploadFile, File()], kind: Annotated[Literal["question", "notes"], Form()],
) -> dict[str, str]:
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "file too large (10 MB max)")
    ctype = sniff(bytes(data[:12]))
    if ctype is None:
        raise HTTPException(415, "only PNG, JPEG, WebP or PDF files")
    try:
        if len(await storage.list(f"{user}/")) >= MAX_FILES:
            raise HTTPException(409, f"upload limit reached ({MAX_FILES} files); delete your data in Privacy to free space")
        upload_id = f"{kind}-{uuid.uuid4().hex}"
        await storage.put(f"{user}/{upload_id}", bytes(data), ctype)
    except StorageError:
        raise HTTPException(502, "could not store the file, try again") from None
    return {"upload_id": upload_id}


@router.get("/uploads/{upload_id}")
async def get_upload(user: UserDep, upload_id: str, storage: StorageDep) -> dict[str, str]:
    if not ID_RE.fullmatch(upload_id):
        raise HTTPException(404, "no such upload")
    try:
        return {"url": await storage.sign(f"{user}/{upload_id}", SIGN_S)}
    except LookupError:
        raise HTTPException(404, "no such upload") from None
    except StorageError as e:
        if e.status in (400, 404):  # Supabase answers a missing object to /sign with 400
            raise HTTPException(404, "no such upload") from None
        raise HTTPException(502, "storage unavailable, try again") from None
