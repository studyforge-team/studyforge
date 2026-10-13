"""NR: Postgres full-text search over a student's own note pages (one chunk per PDF page).

Not wired into the solve agent yet: the solve mount (PR #75) plugs `search` into search_my_notes.
"""

import asyncio

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import note_chunks

MAX_PAGES = 200
MAX_PAGE_CHARS = 20_000


def pdf_pages(data: bytes) -> list[tuple[int, str]]:
    """(page number, text) per page, whitespace-collapsed; empty pages are skipped, numbers stay true.
    Raises pdfium.PdfiumError for an unreadable file."""
    pdf = pdfium.PdfDocument(data)
    try:
        out = []
        for i in range(min(len(pdf), MAX_PAGES)):
            page = pdf[i]
            t = " ".join(page.get_textpage().get_text_range().split())[:MAX_PAGE_CHARS]
            if t:
                out.append((i + 1, t))
        return out
    finally:
        pdf.close()


async def index_upload(engine: AsyncEngine, user_id: str, upload_id: str, data: bytes) -> int:
    """Replace the upload's chunks; returns the number of pages that had text."""
    pages = await asyncio.to_thread(pdf_pages, data)
    async with engine.begin() as conn:
        await conn.execute(note_chunks.delete().where(
            note_chunks.c.user_id == user_id, note_chunks.c.upload_id == upload_id))
        if pages:
            await conn.execute(note_chunks.insert(), [
                {"user_id": user_id, "upload_id": upload_id, "page": p, "text": t} for p, t in pages])
    return len(pages)


_SQL = """
SELECT upload_id, page, left(text, 1500) AS text, ts_rank_cd(tsv, q) AS score
FROM app.note_chunks, {q} AS q
WHERE user_id = :u AND tsv @@ q
ORDER BY score DESC, upload_id, page LIMIT :n"""
_AND = "websearch_to_tsquery('english', :q)"
# Student questions rarely share every word with a slide: OR the stemmed lexemes. Built server-side
# from quoted lexemes, so user text never reaches the SQL string.
_OR = ("to_tsquery('simple', (SELECT string_agg(quote_literal(l), ' | ') "
       "FROM unnest(tsvector_to_array(to_tsvector('english', :q))) AS l))")


async def search(engine: AsyncEngine, user_id: str, query: str, limit: int = 5) -> list[dict[str, object]]:
    async with engine.connect() as conn:
        for q in (_AND, _OR):
            rows = (await conn.execute(text(_SQL.format(q=q)), {"u": user_id, "q": query, "n": limit})).mappings().all()
            if rows:
                return [dict(r) for r in rows]
    return []  # also for empty / stopword-only queries (the OR tsquery is NULL -> no rows)
