"""PgNoticeStore and the notices routes on a real Postgres. Runs only with DATABASE_URL set."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app import db
from app.db import PgNoticeStore, make_engine
from app.main import app
from app.routers import notices

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
N = {"text": "CRE assignment 3 due Fri 5 pm", "source": "paste", "title": None, "url": None}


def test_notice_store_and_routes() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_store())
        _routes()
    finally:
        db._engine = None  # bound to the TestClient's loop
        command.downgrade(CFG, "base")


async def _store() -> None:
    engine = make_engine()
    store = PgNoticeStore(engine)
    a = await store.add("u1", N, 3)
    assert a is not None and a["text"] == N["text"] and a["title"] is None and a["created_at"] is not None
    b = await store.add("u1", N | {"source": "share", "title": "HOD", "url": "https://x.edu/n"}, 3)
    assert b is not None and b["url"] == "https://x.edu/n"
    assert await store.add("u2", N, 3) is not None
    assert await store.add("u1", N, 3) is not None
    assert await store.add("u1", N, 3) is None  # the cap: u1 has 3
    listed = await store.list("u1", 10)
    assert len(listed) == 3 and listed[1]["id"] == b["id"]  # newest first
    assert listed[0]["created_at"] >= listed[1]["created_at"] >= listed[2]["created_at"]
    assert set(listed[0]) == {"id", "text", "source", "title", "url", "created_at"}  # never user_id
    assert len(await store.list("u1", 2)) == 2
    assert len(await store.list("u2", 10)) == 1 and await store.list("nobody", 10) == []
    assert await store.delete("u2", b["id"]) is False  # another user's notice
    assert await store.delete("u1", b["id"]) is True and await store.delete("u1", b["id"]) is False
    assert len(await store.list("u1", 10)) == 2
    # the cap holds under concurrency: 15 posts at once against a cap of 5
    got = await asyncio.gather(*[store.add("racer", N, 5) for _ in range(15)])
    assert sum(g is not None for g in got) == 5 and len(await store.list("racer", 50)) == 5
    await engine.dispose()


def _routes() -> None:
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[notices.current_user] = lambda: "u3"
    try:
        with TestClient(app) as client:  # the real get_store: shared engine on DATABASE_URL
            r = client.post("/api/v1/notices", json={"text": "viva Monday\x00", "source": "share"})
            assert r.status_code == 201 and r.json()["text"] == "viva Monday"
            listed = client.get("/api/v1/notices").json()["notices"]
            assert [n["text"] for n in listed] == ["viva Monday"]
            assert client.delete(f"/api/v1/notices/{listed[0]['id']}").status_code == 204
            assert client.get("/api/v1/notices").json() == {"notices": []}
            assert client.delete("/api/v1/notices/a%00b").status_code == 404  # never reaches Postgres
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
