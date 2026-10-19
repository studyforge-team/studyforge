"""PDF text extraction utilities.

Uses pypdfium2 (already required by the project) to extract the text layer
from a PDF.  Every pdfium call goes through the shared ``one_at_a_time``
lock in ``app.pdfium_lock``.
"""

from __future__ import annotations

import asyncio
import io


async def pdf_pages(data: bytes) -> list[tuple[int, str]]:
    """Return ``[(page_no, text), ...]`` for every page in *data*.

    Page numbers are 1-based.  Pages with no text layer return an empty
    string (they may be scanned images).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _extract_sync, data)


def _extract_sync(data: bytes) -> list[tuple[int, str]]:
    try:
        import pypdfium2 as pdfium  # type: ignore[import]
    except ImportError:
        return []

    try:
        doc = pdfium.PdfDocument(io.BytesIO(data))
    except Exception:  # noqa: BLE001
        return []

    results: list[tuple[int, str]] = []
    for i, page in enumerate(doc, start=1):
        try:
            text_page = page.get_textpage()
            results.append((i, text_page.get_text_range()))
        except Exception:  # noqa: BLE001
            results.append((i, ""))
    return results
