from fastapi.testclient import TestClient

from app.main import app


def test_quiz_answers_503_without_database(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    body = {"answers": ["a"], "score": 1, "correct": [True]}
    assert TestClient(app).post("/api/v1/quizzes/q/answers", json=body).status_code == 503


class _Conn:
    async def execute(self, *_a, **_k):  # type: ignore[no-untyped-def]
        class R:
            def scalar(self) -> dict:  # type: ignore[type-arg]
                return {"items": [{"topic": "A"}, {"topic": "B"}, {"topic": "C"}]}
        return R()


class _Engine:
    def begin(self):  # type: ignore[no-untyped-def]
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def cm():  # type: ignore[no-untyped-def]
            yield _Conn()
        return cm()


def _post(monkeypatch, correct):  # type: ignore[no-untyped-def]
    from app import topics
    from app.routers import quizzes

    seen: list = []  # type: ignore[type-arg]

    async def rec(_c, _u, _s, _r, items):  # type: ignore[no-untyped-def]
        seen.extend(items)
        return len(items)

    monkeypatch.setattr(topics, "record", rec)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    app.dependency_overrides[quizzes.get_engine] = lambda: _Engine()
    app.dependency_overrides[quizzes.current_user] = lambda: "u"
    try:
        r = TestClient(app).post("/api/v1/quizzes/q/answers", json={"answers": ["", "", ""], "score": 0, "correct": correct})
    finally:
        app.dependency_overrides.clear()
    return r, seen


def test_skipped_items_are_not_recorded_and_keep_their_index(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    r, seen = _post(monkeypatch, [True, None, False])
    assert r.status_code == 200 and r.json() == {"recorded": 2}
    assert seen == [(0, "A", True), (2, "C", False)]


def test_all_skipped_records_nothing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    r, seen = _post(monkeypatch, [None, None, None])
    assert r.status_code == 200 and r.json() == {"recorded": 0} and seen == []


def test_wrong_length_is_still_422(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    r, seen = _post(monkeypatch, [True, None])
    assert r.status_code == 422 and seen == []
