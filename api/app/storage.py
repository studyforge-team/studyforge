"""Upload storage. The object path in the bucket is the only record (no DB table):
"<user_id>/<upload_id>". Supabase Storage REST, service-role key (server side only)."""

from typing import Any, Protocol

import httpx


class StorageError(Exception):
    """Never carries headers or the key: str() is safe to log and to return."""

    def __init__(self, msg: str, status: int = 0) -> None:
        super().__init__(msg)
        self.status = status


class Storage(Protocol):
    async def put(self, path: str, data: bytes, content_type: str) -> None: ...
    async def get(self, path: str) -> tuple[bytes, str]: ...  # LookupError if missing
    async def sign(self, path: str, expires_s: int) -> str: ...
    async def list(self, prefix: str) -> list[dict[str, Any]]: ...  # [{name, size}] under prefix
    async def delete_prefix(self, prefix: str) -> None: ...


class SupabaseStorage:
    def __init__(self, http: httpx.AsyncClient, url: str, key: str, bucket: str) -> None:
        self._http = http
        self._base = url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    async def _send(self, method: str, url: str, **kw: Any) -> httpx.Response:
        try:
            r = await self._http.request(method, url, headers=self._headers | kw.pop("headers", {}), **kw)
        except httpx.HTTPError as e:
            raise StorageError(f"storage unreachable ({type(e).__name__})") from None
        # Supabase answers a missing object on GET with 404 or with 400 (body statusCode "404")
        if r.status_code in (400, 404) and method == "GET":
            raise LookupError(url.rsplit("/", 1)[-1])
        if not r.is_success:
            raise StorageError(f"storage {method} failed: HTTP {r.status_code}", r.status_code)
        return r

    def _obj(self, path: str) -> str:
        return f"{self._base}/object/{self._bucket}/{path}"

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        await self._send("POST", self._obj(path), content=data,
                         headers={"Content-Type": content_type, "x-upsert": "false"})

    async def get(self, path: str) -> tuple[bytes, str]:
        r = await self._send("GET", self._obj(path))
        return r.content, r.headers.get("content-type", "application/octet-stream")

    async def sign(self, path: str, expires_s: int) -> str:
        r = await self._send("POST", f"{self._base}/object/sign/{self._bucket}/{path}", json={"expiresIn": expires_s})
        return self._base + r.json()["signedURL"]

    async def list(self, prefix: str) -> list[dict[str, Any]]:
        r = await self._send("POST", f"{self._base}/object/list/{self._bucket}",
                             json={"prefix": prefix, "limit": 1000, "offset": 0})
        # ponytail: one page of 1000; uploads are capped at 20 per user so a prefix never exceeds it
        return [{"name": o["name"], "size": (o.get("metadata") or {}).get("size", 0)} for o in r.json()]

    async def delete_prefix(self, prefix: str) -> None:
        names = [prefix + o["name"] for o in await self.list(prefix)]
        if names:
            await self._send("DELETE", f"{self._base}/object/{self._bucket}", json={"prefixes": names})
