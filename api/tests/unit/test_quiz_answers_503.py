from fastapi.testclient import TestClient

from app.main import app


def test_quiz_answers_503_without_database(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    body = {"answers": ["a"], "score": 1, "correct": [True]}
    assert TestClient(app).post("/api/v1/quizzes/q/answers", json=body).status_code == 503
