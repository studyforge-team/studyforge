from typing import Any

import pytest

from app.storage import StorageError


@pytest.fixture
def anyio_backend() -> str:  # async tests run via the anyio pytest plugin, asyncio only
    return "asyncio"


class MemoryStorage:
    """In-memory app.storage.Storage. fail=True makes every call raise StorageError."""

    def __init__(self) -> None:
        self.objs: dict[str, tuple[bytes, str]] = {}
        self.fail = False

    def _chk(self) -> None:
        if self.fail:
            raise StorageError("boom", 500)

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        self._chk()
        self.objs[path] = (data, content_type)

    async def get(self, path: str) -> tuple[bytes, str]:
        self._chk()
        if path not in self.objs:
            raise LookupError(path)
        return self.objs[path]

    async def sign(self, path: str, expires_s: int) -> str:
        await self.get(path)
        return f"https://signed.example/{path}?exp={expires_s}"

    async def list(self, prefix: str) -> list[dict[str, Any]]:
        self._chk()
        return [{"name": p[len(prefix):], "size": len(d)} for p, (d, _) in self.objs.items() if p.startswith(prefix)]

    async def delete_prefix(self, prefix: str) -> None:
        self._chk()
        self.objs = {p: v for p, v in self.objs.items() if not p.startswith(prefix)}
