"""Unit tests for T4: progress and quiz attempts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_attempt_row(
    quiz_id: str,
    topic: str,
    score: float,
    total: float,
    marks_per_q: float = 1.0,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "quiz_id": quiz_id,
        "topic": topic,
        "score": score,
        "total": total,
        "marks_per_q": marks_per_q,
        "created_at": created_at or datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc),
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
    def __init__(self, rows, topic_order_rows):
        self._rows = rows
        self._topic_order_rows = topic_order_rows
        self._calls = 0

    async def execute(self, query, *a, **kw):
        self._calls += 1
        query_text = str(getattr(query, "text", query))
        if "GROUP BY topic" in query_text or self._calls == 2:
            return FakeResult(self._topic_order_rows)
        return FakeResult(self._rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


class FakeEngine:
    def __init__(self, rows, topic_order_rows):
        self._rows = rows
        self._topic_order_rows = topic_order_rows

    def connect(self):
        return FakeConn(self._rows, self._topic_order_rows)

    @property
    def dialect(self):
        return MagicMock()


def _make_progress_client(rows: list[dict], topic_order: list[dict]) -> TestClient:
    from app.routers import progress as progress_mod
    from app.routers.checkins import _need_db, get_engine
    from app.routers.solve import current_user

    _app = FastAPI()
    _app.include_router(progress_mod.router)

    _app.dependency_overrides[get_engine] = lambda: FakeEngine(rows, topic_order)
    _app.dependency_overrides[current_user] = lambda: "test-user"
    _app.dependency_overrides[_need_db] = lambda: None

    return TestClient(_app)


class TestQuizAttemptsProgress:
    def test_empty_attempts(self):
        client = _make_progress_client([], [])
        resp = client.get("/api/v1/quiz-attempts")
        assert resp.status_code == 200
        assert resp.json() == {"topics": []}

    def test_grouped_by_topic_and_ordered(self):
        rows = [
            _make_attempt_row("q1", "Thermodynamics", 3.0, 5.0, 1.0),
            _make_attempt_row("q2", "Thermodynamics", 4.0, 5.0, 1.0),
            _make_attempt_row("q3", "Heat Transfer", 2.0, 5.0, 2.0),
        ]
        topic_order = [
            {"topic": "Heat Transfer", "latest": datetime(2026, 10, 19, tzinfo=timezone.utc)},
            {"topic": "Thermodynamics", "latest": datetime(2026, 10, 18, tzinfo=timezone.utc)},
        ]
        client = _make_progress_client(rows, topic_order)
        resp = client.get("/api/v1/quiz-attempts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["topics"]) == 2
        # Topic with latest attempt comes first
        assert data["topics"][0]["topic"] == "Heat Transfer"
        assert len(data["topics"][0]["attempts"]) == 1
        assert data["topics"][1]["topic"] == "Thermodynamics"
        assert len(data["topics"][1]["attempts"]) == 2
