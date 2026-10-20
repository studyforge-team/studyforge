"""Integration tests for FO1: practice attempts (POST /api/v1/practice-attempts).

Tests:
- a post is saved and GET /api/v1/quiz-attempts then shows the topic;
- a score above total is stored as total;
- total=0 gives 422;
- another user doesn't see it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql.dml import Insert

from app.routers import practice as practice_mod
from app.routers import progress as progress_mod
from app.routers.checkins import _need_db, get_engine
from app.routers.solve import current_user


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows]


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self._rows)


class FakeConn:
    def __init__(self, storage: list[dict[str, Any]]) -> None:
        self._storage = storage

    async def execute(self, query: Any, params: dict[str, Any] | None = None) -> FakeResult:
        query_str = str(getattr(query, "text", query))
        # Handle insert into quiz_attempts
        if isinstance(query, Insert):
            compiled = query.compile()
            p = dict(compiled.params)
            p.setdefault("created_at", datetime.now(timezone.utc))
            self._storage.append(p)
            return FakeResult([])

        # Handle progress queries:
        u = (params or {}).get("u", "")
        user_rows = [r for r in self._storage if r.get("user_id") == u]

        if "GROUP BY topic" in query_str or "MAX(created_at)" in query_str:
            # Topic order: distinct topics with max created_at
            topic_latest: dict[str, datetime] = {}
            for r in user_rows:
                top = r["topic"]
                cat = r.get("created_at") or datetime.now(timezone.utc)
                if top not in topic_latest or cat > topic_latest[top]:
                    topic_latest[top] = cat
            sorted_topics = sorted(topic_latest.items(), key=lambda kv: kv[1], reverse=True)
            topic_order_rows = [{"topic": t, "latest": dt} for t, dt in sorted_topics]
            return FakeResult(topic_order_rows)

        # Default: user rows sorted by topic, created_at
        sorted_rows = sorted(
            user_rows,
            key=lambda r: (r.get("topic", ""), r.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)),
        )
        return FakeResult(sorted_rows)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *a: object) -> None:
        pass


class FakeEngine:
    def __init__(self, storage: list[dict[str, Any]]) -> None:
        self._storage = storage

    def begin(self) -> FakeConn:
        return FakeConn(self._storage)

    def connect(self) -> FakeConn:
        return FakeConn(self._storage)


def _make_test_client(user_state: dict[str, str], storage: list[dict[str, Any]]) -> TestClient:
    app = FastAPI()
    app.include_router(practice_mod.router)
    app.include_router(progress_mod.router)

    app.dependency_overrides[get_engine] = lambda: FakeEngine(storage)
    app.dependency_overrides[current_user] = lambda: user_state["user"]
    app.dependency_overrides[_need_db] = lambda: None

    return TestClient(app)


def test_practice_attempts_saved_and_retrieved() -> None:
    storage: list[dict[str, Any]] = []
    user_state = {"user": "user-a"}
    client = _make_test_client(user_state, storage)

    # Post practice attempt
    resp = client.post(
        "/api/v1/practice-attempts",
        json={"topic": "OA: ExxonMobil", "score": 12.0, "total": 15, "marks_per_q": 1},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # GET /api/v1/quiz-attempts shows the topic
    progress_resp = client.get("/api/v1/quiz-attempts")
    assert progress_resp.status_code == 200
    data = progress_resp.json()
    assert len(data["topics"]) == 1
    topic_entry = data["topics"][0]
    assert topic_entry["topic"] == "OA: ExxonMobil"
    assert len(topic_entry["attempts"]) == 1
    attempt = topic_entry["attempts"][0]
    assert attempt["score"] == 12.0
    assert attempt["total"] == 15.0
    assert attempt["marks_per_q"] == 1.0


def test_score_above_total_stored_as_total() -> None:
    storage: list[dict[str, Any]] = []
    user_state = {"user": "user-a"}
    client = _make_test_client(user_state, storage)

    # Post practice attempt with score > total
    resp = client.post(
        "/api/v1/practice-attempts",
        json={"topic": "OA: Shell", "score": 25.0, "total": 15, "marks_per_q": 1},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Verify score is clamped to total (15.0) in storage and progress
    progress_resp = client.get("/api/v1/quiz-attempts")
    assert progress_resp.status_code == 200
    attempt = progress_resp.json()["topics"][0]["attempts"][0]
    assert attempt["score"] == 15.0
    assert attempt["total"] == 15.0


def test_total_zero_gives_422() -> None:
    storage: list[dict[str, Any]] = []
    user_state = {"user": "user-a"}
    client = _make_test_client(user_state, storage)

    # total=0 must fail validation (Field(ge=1, le=50))
    resp = client.post(
        "/api/v1/practice-attempts",
        json={"topic": "OA: Chevron", "score": 0.0, "total": 0, "marks_per_q": 1},
    )
    assert resp.status_code == 422


def test_another_user_does_not_see_it() -> None:
    storage: list[dict[str, Any]] = []
    user_state = {"user": "user-a"}
    client = _make_test_client(user_state, storage)

    # user-a posts
    resp = client.post(
        "/api/v1/practice-attempts",
        json={"topic": "OA: BP", "score": 10.0, "total": 15, "marks_per_q": 1},
    )
    assert resp.status_code == 200

    # user-b reads
    user_state["user"] = "user-b"
    progress_resp = client.get("/api/v1/quiz-attempts")
    assert progress_resp.status_code == 200
    data = progress_resp.json()
    assert data["topics"] == []
