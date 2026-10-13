import json
import struct
import zlib
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.routers import uploads
from app.storage import StorageError, SupabaseStorage
from tests.unit.conftest import MemoryStorage

pytestmark = pytest.mark.anyio
Env = tuple[FastAPI, MemoryStorage, dict[str, str]]


def _png() -> bytes:
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20 + b"\xff\xd9"
WEBP = b"RIFF" + struct.pack("<I", 12) + b"WEBPVP8 " + b"\x00" * 8
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
MB10 = 10 * 1024 * 1024


@pytest.fixture
def env() -> Env:
    app, mem, who = FastAPI(), MemoryStorage(), {"u": "A"}
    app.include_router(uploads.router)
    app.dependency_overrides[uploads.get_storage] = lambda: mem
    app.dependency_overrides[uploads.current_user] = lambda: who["u"]
    return app, mem, who


def cl(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def up(c: httpx.AsyncClient, data: bytes, name: str = "f.bin", kind: str = "question",
             ctype: str = "application/octet-stream") -> httpx.Response:
    return await c.post("/api/v1/uploads", files={"file": (name, data, ctype)}, data={"kind": kind})


@pytest.mark.parametrize("data,ctype,kind", [
    (_png(), "image/png", "question"), (JPEG, "image/jpeg", "question"),
    (WEBP, "image/webp", "question"), (PDF, "application/pdf", "question"),
    (PDF + b"notes", "application/pdf", "notes"),
])
async def test_upload_then_display(env: Env, data: bytes, ctype: str, kind: str) -> None:
    app, mem, _ = env
    async with cl(app) as c:
        # the client lies about the type: the stored type is the sniffed one
        r = await up(c, data, "x.txt", kind, "text/plain")
        assert r.status_code == 200
        uid = r.json()["upload_id"]
        assert uid.startswith(kind + "-")
        assert mem.objs[f"A/{uid}"] == (data, ctype)
        g = await c.get(f"/api/v1/uploads/{uid}")
        assert g.status_code == 200 and g.json()["url"].startswith("https://signed.example/A/" + uid)
        assert "exp=600" in g.json()["url"]
    assert await uploads.fetch_upload(mem, "A", uid) == (data, ctype)


async def test_size_cap(env: Env) -> None:
    app, mem, _ = env
    async with cl(app) as c:
        assert (await up(c, b"%PDF-" + b"0" * (MB10 - 5))).status_code == 200  # exactly 10 MB
        assert (await up(c, b"%PDF-" + b"0" * (MB10 - 4))).status_code == 413  # 10 MB + 1
    assert len(mem.objs) == 1


async def test_declared_content_length_rejected_before_reading(env: Env) -> None:
    app, mem, _ = env
    async with cl(app) as c:
        r = await c.post("/api/v1/uploads", content=b"x", headers={
            "content-length": str(MB10 + 600 * 1024), "content-type": "multipart/form-data; boundary=b"})
    assert r.status_code == 413 and not mem.objs


@pytest.mark.parametrize("name,data", [
    ("a.png", b"this is just text"), ("a.html", b"<html><script>1</script></html>"),
    ("a.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>'), ("a.pdf", b""),
    ("a.png", b"RIFF\x00\x00\x00\x00WAVEfmt "),
])
async def test_not_an_allowed_type_415(env: Env, name: str, data: bytes) -> None:
    app, mem, _ = env
    async with cl(app) as c:
        assert (await up(c, data, name, ctype="image/png")).status_code == 415
    assert not mem.objs


async def test_bad_kind_422_and_no_user_401(env: Env) -> None:
    app, mem, _ = env
    async with cl(app) as c:
        assert (await up(c, PDF, kind="avatar")).status_code == 422
    app.dependency_overrides.pop(uploads.current_user)  # the router's own default
    async with cl(app) as c:
        assert (await up(c, PDF)).status_code == 401
        assert (await c.get("/api/v1/uploads/notes-" + "a" * 32)).status_code == 401
    assert not mem.objs


async def test_per_user_cap_and_isolation(env: Env) -> None:
    app, mem, who = env
    async with cl(app) as c:
        ids = [(await up(c, PDF)).json()["upload_id"] for _ in range(20)]
        r = await up(c, PDF)
        assert r.status_code == 409 and "limit" in r.json()["detail"]
        who["u"] = "B"  # own quota; cannot see A's files
        assert (await up(c, PDF)).status_code == 200
        assert (await c.get(f"/api/v1/uploads/{ids[0]}")).status_code == 404
    with pytest.raises(LookupError):
        await uploads.fetch_upload(mem, "B", ids[0])
    assert len([p for p in mem.objs if p.startswith("A/")]) == 20


@pytest.mark.parametrize("bad", [
    "../x", "question-../../a", "question-" + "A" * 32, "question-" + "a" * 31, "notes-" + "a" * 33,
    "x-" + "a" * 32, "question-" + "a" * 32 + "%0A",
])
async def test_bad_ids_404(env: Env, bad: str) -> None:
    app, mem, _ = env
    mem.objs["A/../x"] = (PDF, "application/pdf")
    async with cl(app) as c:
        assert (await c.get(f"/api/v1/uploads/{bad}")).status_code == 404
    with pytest.raises(LookupError):
        await uploads.fetch_upload(mem, "A", bad)


async def test_storage_failure_502_and_missing_env_503(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    app, mem, _ = env
    mem.fail = True
    async with cl(app) as c:
        assert (await up(c, PDF)).status_code == 502
    app.dependency_overrides.pop(uploads.get_storage)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    async with cl(app) as c:
        r = await up(c, PDF)
        assert r.status_code == 503 and r.json() == {"detail": "not available"}
    monkeypatch.setenv("SUPABASE_URL", "https://p.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    async with cl(app) as c:
        assert (await c.get("/api/v1/uploads/notes-" + "a" * 32)).status_code == 503


# --- SupabaseStorage against the REST contract ---

KEY = "svc-secret-key"


def sb(handler: Any) -> tuple[SupabaseStorage, list[httpx.Request]]:
    reqs: list[httpx.Request] = []

    def h(req: httpx.Request) -> httpx.Response:
        reqs.append(req)
        return handler(req)  # type: ignore[no-any-return]
    return SupabaseStorage(httpx.AsyncClient(transport=httpx.MockTransport(h)), "https://p.supabase.co/", KEY, "uploads"), reqs


def _auth(r: httpx.Request) -> None:
    assert r.headers["apikey"] == KEY and r.headers["authorization"] == f"Bearer {KEY}"


async def test_supabase_put_get() -> None:
    s, reqs = sb(lambda r: httpx.Response(200, content=b"zz", headers={"content-type": "image/png"}))
    await s.put("A/question-1", b"data", "image/png")
    r = reqs[0]
    assert r.method == "POST" and str(r.url) == "https://p.supabase.co/storage/v1/object/uploads/A/question-1"
    assert r.content == b"data" and r.headers["content-type"] == "image/png" and r.headers["x-upsert"] == "false"
    _auth(r)
    assert await s.get("A/question-1") == (b"zz", "image/png")
    assert reqs[1].method == "GET" and str(reqs[1].url) == str(r.url)
    _auth(reqs[1])


async def test_supabase_get_404_is_lookup_error() -> None:
    s, _ = sb(lambda r: httpx.Response(404, json={"error": "not_found"}))
    with pytest.raises(LookupError):
        await s.get("A/x")


async def test_supabase_sign_prefixes_url() -> None:
    s, reqs = sb(lambda r: httpx.Response(200, json={"signedURL": "/object/sign/uploads/A/q?token=t"}))
    assert await s.sign("A/q", 600) == "https://p.supabase.co/storage/v1/object/sign/uploads/A/q?token=t"
    r = reqs[0]
    assert r.method == "POST" and str(r.url) == "https://p.supabase.co/storage/v1/object/sign/uploads/A/q"
    assert json.loads(r.content) == {"expiresIn": 600}
    _auth(r)


async def test_supabase_list_and_delete_prefix() -> None:
    def h(r: httpx.Request) -> httpx.Response:
        if r.url.path.endswith("/object/list/uploads"):
            return httpx.Response(200, json=[{"name": "q1", "metadata": {"size": 5}}, {"name": "n2", "metadata": None}])
        return httpx.Response(200, json=[])
    s, reqs = sb(h)
    assert await s.list("A/") == [{"name": "q1", "size": 5}, {"name": "n2", "size": 0}]
    assert json.loads(reqs[0].content) == {"prefix": "A/", "limit": 1000, "offset": 0}
    await s.delete_prefix("A/")
    d = reqs[-1]
    assert d.method == "DELETE" and str(d.url) == "https://p.supabase.co/storage/v1/object/uploads"
    assert json.loads(d.content) == {"prefixes": ["A/q1", "A/n2"]}
    _auth(d)


async def test_supabase_delete_prefix_empty_sends_no_delete() -> None:
    s, reqs = sb(lambda r: httpx.Response(200, json=[]))
    await s.delete_prefix("A/")
    assert [r.method for r in reqs] == ["POST"]


async def test_supabase_error_never_leaks_key() -> None:
    s, _ = sb(lambda r: httpx.Response(400, json={"message": "bad"}))
    with pytest.raises(StorageError) as e:
        await s.put("A/q", b"x", "image/png")
    assert KEY not in str(e.value) and "400" in str(e.value) and e.value.status == 400

    def boom(r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down " + KEY, request=r)
    s2 = SupabaseStorage(httpx.AsyncClient(transport=httpx.MockTransport(boom)), "https://p", KEY, "uploads")
    with pytest.raises(StorageError) as e2:
        await s2.list("A/")
    assert KEY not in str(e2.value)
