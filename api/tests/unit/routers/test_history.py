"""Unit tests for T5: GET /api/v1/solves history endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Fake DB ───────────────────────────────────────────────────────────────────

def _make_row(
    id: str,
    question: str,
    status: str = "final",
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "question": question,
        "status": status,
        "updated_at": updated_at or datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc),
    }


class FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return [dict(row) for row in self._rows]


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return FakeMappings(self._rows)


class FakeConn:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, *a, **kw):
        return FakeResult(self._rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


class FakeEngine:
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return FakeConn(self._rows)

    @property
    def dialect(self):
        return MagicMock()


# ── App fixture ───────────────────────────────────────────────────────────────

def _make_client(rows: list[dict]) -> TestClient:
    from app.routers import history as history_mod
    from app.routers.checkins import get_engine
    from app.routers.dashboard import _need_db
    from app.routers.solve import current_user

    _app = FastAPI()
    _app.include_router(history_mod.router)

    _app.dependency_overrides[get_engine] = lambda: FakeEngine(rows)
    _app.dependency_overrides[current_user] = lambda: "test-user"
    _app.dependency_overrides[_need_db] = lambda: None

    return TestClient(_app)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestListSolves:
    def test_empty_result(self):
        client = _make_client([])
        resp = client.get("/api/v1/solves")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"items": [], "next": None}

    def test_returns_items(self):
        rows = [
            _make_row("s1", "CSTR first order", updated_at=datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)),
            _make_row("s2", "Heat exchanger", updated_at=datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)),
        ]
        client = _make_client(rows)
        resp = client.get("/api/v1/solves")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        assert items[0]["id"] == "s1"
        assert items[0]["question"] == "CSTR first order"

    def test_next_cursor_none_when_fewer_than_21(self):
        rows = [_make_row(f"s{i}", f"Q{i}") for i in range(5)]
        client = _make_client(rows)
        resp = client.get("/api/v1/solves")
        assert resp.json()["next"] is None

    def test_next_cursor_set_when_21_rows(self):
        rows = [
            _make_row(f"s{i}", f"Q{i}", updated_at=datetime(2026, 10, i + 1, tzinfo=timezone.utc))
            for i in range(21)
        ]
        client = _make_client(rows)
        resp = client.get("/api/v1/solves")
        data = resp.json()
        # 20 items returned, next is set
        assert len(data["items"]) == 20
        assert data["next"] is not None

    def test_state_not_returned(self):
        """Never return the full state object."""
        rows = [_make_row("s1", "Q1")]
        client = _make_client(rows)
        resp = client.get("/api/v1/solves")
        item = resp.json()["items"][0]
        assert "state" not in item
        assert "figures" not in item
        assert "answer_md" not in item
