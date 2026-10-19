"""Unit tests for T1: POST /api/v1/quizzes.

Covers:
- topic-only request
- kinds parameter reaches the generator
- defaults (n_items=5, kinds='mcq', marks_per_q=1)
- 503 when no model configured
- 422 for validation errors
- upload_id=None path
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.agent.quiz import MCQItem, Quiz
from app.agent.quiz_gen import QuizGenerationFailed

# ── Fake LLM ─────────────────────────────────────────────────────────────────

def _make_mcq_item(topic: str = "Thermodynamics") -> MCQItem:
    return MCQItem(
        type="mcq",
        topic=topic,
        stem="What is the first law of thermodynamics?",
        source=None,
        tags=[],
        options=["Energy conservation", "Entropy increase", "Zero entropy", "Heat death"],
        correct_index=0,
        misconceptions={1: "Entropy, not energy", 2: "Third law", 3: "Heat death is different"},
        explanation="Energy cannot be created or destroyed.",
    )


def _make_quiz(n: int = 3) -> Quiz:
    return Quiz(
        title="Thermodynamics Quiz",
        items=[_make_mcq_item() for _ in range(n)],
    )


class FakeLLM:
    """Fake ChatJSON that returns a pre-built quiz."""

    def __init__(self, quiz: Quiz | None = None, fail: bool = False) -> None:
        self._quiz = quiz or _make_quiz()
        self._fail = fail
        self.calls: list[dict[str, Any]] = []

    async def chat_json(self, role, messages, schema, *, deadline=None, solve_id=None):
        self.calls.append({"role": role, "messages": messages, "schema": schema})
        if self._fail:
            raise QuizGenerationFailed("test failure")
        return self._quiz, {}


# ── Fake DB engine ────────────────────────────────────────────────────────────

class FakeConn:
    async def execute(self, *a, **kw):
        class Result:
            def fetchone(self):
                return None
        return Result()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


class FakeEngine:
    def begin(self):
        return FakeConn()

    def connect(self):
        return FakeConn()

    @property
    def dialect(self):
        return MagicMock()


# ── App fixture ───────────────────────────────────────────────────────────────

@pytest.fixture()
def client_with_llm():
    """TestClient with a working fake LLM and fake DB."""
    from fastapi import FastAPI

    from app.routers import quiz_new as qn
    from app.routers.checkins import _need_db, get_engine
    from app.routers.prep import get_llm
    from app.routers.solve import current_user, spend_context
    from app.routers.uploads import get_storage

    _app = FastAPI()
    _app.include_router(qn.router)

    fake_llm = FakeLLM()
    fake_engine = FakeEngine()

    _app.dependency_overrides[get_engine] = lambda: fake_engine
    _app.dependency_overrides[get_llm] = lambda: fake_llm
    _app.dependency_overrides[current_user] = lambda: "test-user"
    _app.dependency_overrides[spend_context] = lambda: None
    _app.dependency_overrides[_need_db] = lambda: None
    _app.dependency_overrides[get_storage] = lambda: MagicMock()

    return TestClient(_app), fake_llm


@pytest.fixture()
def client_no_llm():
    """TestClient with no LLM (None)."""
    from fastapi import FastAPI

    from app.routers import quiz_new as qn
    from app.routers.checkins import _need_db, get_engine
    from app.routers.prep import get_llm
    from app.routers.solve import current_user, spend_context
    from app.routers.uploads import get_storage

    _app = FastAPI()
    _app.include_router(qn.router)

    _app.dependency_overrides[get_engine] = lambda: FakeEngine()
    _app.dependency_overrides[get_llm] = lambda: None
    _app.dependency_overrides[current_user] = lambda: "test-user"
    _app.dependency_overrides[spend_context] = lambda: None
    _app.dependency_overrides[_need_db] = lambda: None
    _app.dependency_overrides[get_storage] = lambda: MagicMock()

    return TestClient(_app)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateQuiz:
    def test_topic_only_returns_200(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post("/api/v1/quizzes", json={"topic": "Thermodynamics"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["topic"] == "Thermodynamics"
        assert data["marks_per_q"] == 1
        assert data["total_marks"] == len(data["items"]) * 1
        assert "suggested_minutes" in data
        assert len(data["items"]) >= 1

    def test_defaults_applied(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post("/api/v1/quizzes", json={"topic": "Heat transfer"})
        assert resp.status_code == 200
        data = resp.json()
        # Default: n_items=5, kinds='mcq', marks_per_q=1
        assert data["marks_per_q"] == 1
        assert data["suggested_minutes"] == len(data["items"]) * 2  # mcq = 2 min

    def test_kinds_reaches_generator(self, client_with_llm):
        """The kinds parameter must appear in the LLM messages."""
        client, fake_llm = client_with_llm
        resp = client.post(
            "/api/v1/quizzes",
            json={"topic": "Mass transfer", "kinds": "blank"},
        )
        assert resp.status_code == 200
        assert fake_llm.calls, "LLM was not called"
        user_content = fake_llm.calls[-1]["messages"][-1]["content"]
        # The kinds instruction should be in the user message
        assert "blank" in user_content.lower() or "fill-in" in user_content.lower()

    def test_blank_kinds_suggested_time(self, client_with_llm):
        """blank kinds → suggested_minutes = n * 3."""
        client, _ = client_with_llm
        resp = client.post(
            "/api/v1/quizzes",
            json={"topic": "Process control", "kinds": "blank", "n_items": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggested_minutes"] == len(data["items"]) * 3

    def test_503_when_no_llm(self, client_no_llm):
        resp = client_no_llm.post("/api/v1/quizzes", json={"topic": "Anything"})
        assert resp.status_code == 503
        assert resp.json()["detail"] == "quiz not available"

    def test_422_topic_too_short(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post("/api/v1/quizzes", json={"topic": ""})
        assert resp.status_code == 422

    def test_422_topic_too_long(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post("/api/v1/quizzes", json={"topic": "x" * 81})
        assert resp.status_code == 422

    def test_422_n_items_out_of_range(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post("/api/v1/quizzes", json={"topic": "CRE", "n_items": 1})
        assert resp.status_code == 422

    def test_422_extra_field_forbidden(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post(
            "/api/v1/quizzes", json={"topic": "CRE", "unknown_field": "bad"}
        )
        assert resp.status_code == 422

    def test_marks_per_q_in_response(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post(
            "/api/v1/quizzes", json={"topic": "CRE", "marks_per_q": 4}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["marks_per_q"] == 4
        assert data["total_marks"] == len(data["items"]) * 4

    def test_invalid_kinds(self, client_with_llm):
        client, _ = client_with_llm
        resp = client.post(
            "/api/v1/quizzes", json={"topic": "CRE", "kinds": "essay"}
        )
        assert resp.status_code == 422
