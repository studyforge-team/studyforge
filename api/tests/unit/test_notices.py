import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import notices


class Store:
    """In-memory stand-in for db.PgNoticeStore (the real one is covered in tests/integration).
    Ids are uuid4 hex, as in the real store."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def add(self, user_id: str, notice: dict[str, Any], limit: int) -> dict[str, Any] | None:
        if sum(r["user_id"] == user_id for r in self.rows) >= limit:
            return None
        row = {"id": f"{len(self.rows):032x}", "user_id": user_id, **notice,
               "created_at": datetime(2026, 10, 13, 9, len(self.rows), tzinfo=UTC)}
        self.rows.append(row)
        return row

    async def delete(self, user_id: str, notice_id: str) -> bool:
        hit = [r for r in self.rows if r["id"] == notice_id and r["user_id"] == user_id]
        self.rows = [r for r in self.rows if r not in hit]
        return bool(hit)

    async def list(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        mine = [r for r in self.rows if r["user_id"] == user_id]
        return sorted(mine, key=lambda r: r["created_at"], reverse=True)[:limit]


@pytest.fixture
def setup() -> Iterator[tuple[TestClient, Store, dict[str, str]]]:
    store, who = Store(), {"user": "u1"}
    saved = dict(app.dependency_overrides)  # main.py's production wiring, restored afterwards
    app.dependency_overrides[notices.get_store] = lambda: store
    app.dependency_overrides[notices.current_user] = lambda: who["user"]
    try:
        yield TestClient(app), store, who
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def test_post_then_list_newest_first(setup: tuple[TestClient, Store, dict[str, str]]) -> None:
    client, store, _ = setup
    r = client.post("/api/v1/notices", json={"text": "  CRE assignment 3 due Fri 5 pm  "})
    assert r.status_code == 201
    body = r.json()
    assert body["text"] == "CRE assignment 3 due Fri 5 pm"  # trimmed
    assert body["source"] == "paste" and body["title"] is None and body["url"] is None
    assert set(body) == {"id", "text", "source", "title", "url", "created_at"}  # no user_id on the wire
    r = client.post("/api/v1/notices", json={
        "text": "Lab viva moved to Monday", "source": "share", "title": "HOD", "url": "https://example.edu/n/1",
    })
    assert r.status_code == 201
    listed = client.get("/api/v1/notices").json()["notices"]
    assert [n["text"] for n in listed] == ["Lab viva moved to Monday", "CRE assignment 3 due Fri 5 pm"]
    assert listed[0]["source"] == "share" and listed[0]["url"] == "https://example.edu/n/1"
    assert store.rows[0]["user_id"] == "u1"


def test_users_only_see_their_own(setup: tuple[TestClient, Store, dict[str, str]]) -> None:
    client, _, who = setup
    client.post("/api/v1/notices", json={"text": "mine"})
    who["user"] = "u2"
    assert client.get("/api/v1/notices").json() == {"notices": []}


@pytest.mark.parametrize("body", [
    {"text": ""},
    {"text": "   \n "},  # blank after trimming
    {"text": "x" * (notices.MAX_TEXT + 1)},
    {"text": "ok", "source": "email"},
    {"text": "ok", "url": "javascript:alert(1)"},  # shown as a link: only http(s)
    {"text": "ok", "url": "ftp://x.y/z"},
    {"text": "ok", "url": "https://"},  # no host
    {"text": "ok", "url": "https://a.b/c d"},  # whitespace hidden in a link
    {"text": "ok", "url": "https://a.b/\nx"},
    {"text": "ok", "url": "https://a.b/\u007fx"},  # DEL
    {"text": "ok", "url": "https://a.b/\u00a0x"},  # no-break space
    {"text": "ok", "url": "https://a.b:99999/"},
    {"text": "ok", "url": "http://[::1/"},
    {"text": " " + "x" * notices.MAX_TEXT},  # the limit counts the text as sent
    {"text": "ok", "title": "t" * 201},
    {"text": "ok", "user_id": "someone-else"},  # unknown fields refused, never trusted
    {},
])
def test_bad_bodies_are_refused(setup: tuple[TestClient, Store, dict[str, str]], body: dict[str, Any]) -> None:
    client, store, _ = setup
    assert client.post("/api/v1/notices", json=body).status_code == 422
    assert store.rows == []


@pytest.mark.parametrize("raw", [
    b'{"text": "a\\ud800b"}',  # lone surrogate: valid JSON, not storable as UTF-8
    b'{"text": "ok", "title": "\\udfff"}',
    b'{"text": "ok"',  # not JSON
    b'["text"]',
    b"",
])
def test_bad_json_is_422_not_500(setup: tuple[TestClient, Store, dict[str, str]], raw: bytes) -> None:
    client, store, _ = setup
    r = client.post("/api/v1/notices", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and store.rows == []


def test_nul_bytes_are_removed(setup: tuple[TestClient, Store, dict[str, str]]) -> None:
    client, _, _ = setup  # Postgres text cannot hold NUL; a pasted binary snippet must not cause a 500
    r = client.post("/api/v1/notices", json={"text": "a\x00b", "title": "t\x00"})
    assert r.status_code == 201 and r.json()["text"] == "ab" and r.json()["title"] == "t"
    assert client.post("/api/v1/notices", json={"text": "\x00"}).status_code == 422


def test_per_user_cap(setup: tuple[TestClient, Store, dict[str, str]], monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, who = setup
    monkeypatch.setattr(notices, "MAX_PER_USER", 2)
    for _ in range(2):
        assert client.post("/api/v1/notices", json={"text": "x"}).status_code == 201
    r = client.post("/api/v1/notices", json={"text": "x"})
    assert r.status_code == 429
    who["user"] = "u2"  # the cap is per user
    assert client.post("/api/v1/notices", json={"text": "x"}).status_code == 201


def test_list_is_capped(setup: tuple[TestClient, Store, dict[str, str]], monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = setup
    monkeypatch.setattr(notices, "LIST_LIMIT", 3)
    for i in range(5):
        client.post("/api/v1/notices", json={"text": str(i)})
    assert [n["text"] for n in client.get("/api/v1/notices").json()["notices"]] == ["4", "3", "2"]


def test_sign_in_required() -> None:
    client = TestClient(app)  # production wiring: auth.current_user, no token
    assert client.get("/api/v1/notices").status_code == 401
    assert client.post("/api/v1/notices", json={"text": "x"}).status_code == 401
    assert client.delete("/api/v1/notices/" + "0" * 32).status_code == 401


def test_no_database_is_503(setup: tuple[TestClient, Store, dict[str, str]], monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = setup
    del app.dependency_overrides[notices.get_store]  # the real dependency, with DATABASE_URL unset
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert client.get("/api/v1/notices").status_code == 503
    assert client.post("/api/v1/notices", json={"text": "x"}).status_code == 503


def test_errors_do_not_echo_the_input(setup: tuple[TestClient, Store, dict[str, str]]) -> None:
    client, _, _ = setup
    r = client.post("/api/v1/notices", json={"text": "secret-notice-" + "x" * notices.MAX_TEXT})
    assert r.status_code == 422 and "secret-notice" not in r.text


def test_oversized_body_is_413(setup: tuple[TestClient, Store, dict[str, str]]) -> None:
    client, store, _ = setup
    r = client.post("/api/v1/notices", json={"text": "x" * (notices.MAX_BODY + 1)})
    assert r.status_code == 413 and store.rows == []

    def chunks() -> Iterator[bytes]:  # no Content-Length (chunked upload): reading still stops past the limit
        yield b'{"text": "'
        for _ in range(100):
            yield b"x" * 1024
    r = client.post("/api/v1/notices", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    # the largest valid notice still fits under the byte limit, even JSON-escaped (6 bytes per char)
    big = {"text": "\u2603" * notices.MAX_TEXT, "title": "t" * 200, "url": "https://a.b/" + "c" * 1900}
    assert len(json.dumps(big).encode()) <= notices.MAX_BODY
    assert client.post("/api/v1/notices", json=big).status_code == 201


def test_delete_only_own(setup: tuple[TestClient, Store, dict[str, str]]) -> None:
    client, store, who = setup
    nid = client.post("/api/v1/notices", json={"text": "oops, wrong paste"}).json()["id"]
    who["user"] = "u2"
    assert client.delete(f"/api/v1/notices/{nid}").status_code == 404  # not yours: same answer as missing
    assert len(store.rows) == 1
    who["user"] = "u1"
    assert client.delete(f"/api/v1/notices/{nid}").status_code == 204
    assert client.delete(f"/api/v1/notices/{nid}").status_code == 404
    assert client.get("/api/v1/notices").json() == {"notices": []}


@pytest.mark.parametrize("bad", ["a%00b", "x" * 33, "ABCDEF" + "0" * 26, "%ED%A0%80"])
def test_delete_odd_ids_are_404(setup: tuple[TestClient, Store, dict[str, str]], bad: str) -> None:
    client, _, _ = setup
    assert client.delete(f"/api/v1/notices/{bad}").status_code == 404


def test_openapi_documents_the_body() -> None:
    spec = TestClient(app).get("/openapi.json").json()
    body = spec["paths"]["/api/v1/notices"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert set(body["properties"]) == {"text", "source", "title", "url"}
