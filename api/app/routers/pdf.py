"""PY and TE: read a PDF the student picks, for its page count, word count and text per page.

POST /api/v1/pdf/read (multipart: file) -> {"pages", "words", "text"}

Nothing is stored: the file is read in memory and dropped. Same size guard and sign-in as C1
uploads. Text comes from the PDF's own text layer (a scanned paper has none: words 0).
"""

import asyncio
from typing import Annotated, Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.notes import MAX_PAGE_CHARS, MAX_PAGES
from app.pdfium_lock import one_at_a_time
from app.routers.uploads import MAX_BYTES, UserDep, _SizeGuardRoute, sniff

router = APIRouter(prefix="/api/v1", route_class=_SizeGuardRoute)
_busy = asyncio.Lock()  # one PDF in memory at a time on Render free (pdfium itself: app/pdfium_lock.py)


def _lines(raw: str) -> str:
    return "\n".join(" ".join(ln.split()) for ln in raw.splitlines() if ln.strip())


@one_at_a_time
def read(data: bytes) -> dict[str, Any]:
    """pages: the true page count. text: one entry per page (first MAX_PAGES); line breaks kept (PY
    splits questions by line), spaces within a line collapsed, blank lines dropped.
    words: counted over those pages. Raises pdfium.PdfiumError for an unreadable or locked file."""
    pdf = pdfium.PdfDocument(data)
    try:
        text = [_lines(pdf[i].get_textpage().get_text_range())[:MAX_PAGE_CHARS]
                for i in range(min(len(pdf), MAX_PAGES))]
        return {"pages": len(pdf), "words": sum(len(t.split()) for t in text), "text": text}
    finally:
        pdf.close()


@router.post("/pdf/read")
async def read_pdf(user: UserDep, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "file too large (10 MB max)")
    if sniff(bytes(data[:12])) != "application/pdf":
        raise HTTPException(415, "only PDF files")
    try:
        async with _busy:
            return await asyncio.to_thread(read, bytes(data))
    except pdfium.PdfiumError:
        raise HTTPException(415, "the PDF could not be read") from None
