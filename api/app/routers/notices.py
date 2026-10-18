"""In-app intake (D1): a notice is text a student pastes into StudyForge, or shares to it from
another app (a class WhatsApp message, an email about a deadline). It is stored as given; nothing
reads it yet. Turning notices into tasks and reminders is a later ticket and needs a model.

POST   /api/v1/notices {text, source?, title?, url?} -> 201 notice
GET    /api/v1/notices -> {notices: [newest first, at most LIST_LIMIT]}
DELETE /api/v1/notices/{id} -> 204 (404 if it is not one of yours)
"""

import os
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.db import PgNoticeStore, shared_engine

MAX_TEXT = 5000  # a long college circular fits; a whole PDF pasted does not
MAX_PER_USER = 500  # abuse cap on a free-tier database
LIST_LIMIT = 50
MAX_BODY = 64 * 1024  # bytes: 5000 characters of any script, JSON-escaped, plus title and url

router = APIRouter(prefix="/api/v1")


def current_user() -> str:  # main.py overrides with auth.current_user (same pattern as solve.py)
    raise HTTPException(status_code=401, detail="not signed in")


def get_store() -> PgNoticeStore:
    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(503, "not available")
    return PgNoticeStore(shared_engine())


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    try:
        v.encode("utf-8")  # a lone surrogate (valid JSON "\\ud800") cannot be stored: 422, not 500
    except UnicodeEncodeError:
        raise ValueError("text is not valid Unicode") from None
    return v.replace("\x00", "").strip()  # Postgres text cannot hold NUL


class NoticeIn(BaseModel):
    # extra="forbid": e.g. a user_id in the body is refused, never trusted.
    # Length limits apply to the text as sent, before trimming.
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=MAX_TEXT)
    source: Literal["paste", "share"] = "paste"
    title: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = _clean(v) or ""
        if not v:
            raise ValueError("text is empty")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return _clean(v) or None

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        v = _clean(v) or None
        if v is None:
            return None
        parts = urlsplit(v)  # the page shows it as a link: http(s) with a host, nothing hidden in it
        hidden = not v.isprintable() or any(c.isspace() for c in v)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname or hidden:
            raise ValueError("url must be an http(s) address")
        _ = parts.port  # ValueError (so 422) for a port outside 0-65535
        return v


class Notice(BaseModel):
    id: str
    text: str
    source: str
    title: str | None
    url: str | None
    created_at: datetime


UserDep = Annotated[str, Depends(current_user)]
StoreDep = Annotated[PgNoticeStore, Depends(get_store)]


@router.post(
    "/notices", status_code=201,  # the body is read by hand below; documented for /docs here
    openapi_extra={"requestBody": {"required": True, "content": {"application/json": {"schema": NoticeIn.model_json_schema()}}}},
)
async def add_notice(user: UserDep, request: Request, store: StoreDep) -> Notice:
    # Read and validate the body here (like POST /solve/{id}/result): reading stops past MAX_BODY,
    # and the 422 names the bad field without echoing the pasted text back.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY:
        raise HTTPException(413, "notice too large")
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > MAX_BODY:
            raise HTTPException(413, "notice too large")
    try:
        body = NoticeIn.model_validate_json(bytes(raw))
    except ValidationError as err:
        fields = sorted({".".join(map(str, e["loc"])) or "body" for e in err.errors(include_input=False)})
        raise HTTPException(422, f"invalid notice: {', '.join(fields)}") from None
    row: dict[str, Any] | None = await store.add(user, body.model_dump(), MAX_PER_USER)
    if row is None:
        raise HTTPException(429, f"notice limit reached ({MAX_PER_USER})")
    return Notice(**row)


@router.get("/notices")
async def list_notices(user: UserDep, store: StoreDep) -> dict[str, list[Notice]]:
    return {"notices": [Notice(**r) for r in await store.list(user, LIST_LIMIT)]}


@router.delete("/notices/{notice_id}", status_code=204)
async def delete_notice(user: UserDep, notice_id: str, store: StoreDep) -> Response:
    # ids are uuid4 hex; anything else (a NUL Postgres cannot take, a huge string) is simply not found
    if not re.fullmatch(r"[0-9a-f]{32}", notice_id) or not await store.delete(user, notice_id):
        raise HTTPException(404, "no such notice")  # also another user's: never says which
    return Response(status_code=204)
