"""Shared asyncio lock for pdfium calls.

pdfium is not thread-safe; every call must go through this lock so that
parallel requests do not corrupt the PDF renderer state.
"""

import asyncio

_lock = asyncio.Lock()


async def one_at_a_time(coro):  # type: ignore[no-untyped-def]
    """Run ``coro`` under the pdfium lock and return its result."""
    async with _lock:
        return await coro
