import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_loop import GOOD, Clock, FakeLLM, calc, tool

from app.agent.loop import Deps
from app.agent.state import InMemoryStore
from app.routers import solve


def client_for(llm: FakeLLM, user: str = "u1") -> tuple[TestClient, Deps]:
    deps = Deps(llm=llm, store=InMemoryStore(), clock=Clock())
    app = FastAPI()
    app.include_router(solve.router)
    app.dependency_overrides[solve.get_deps] = lambda: deps
    app.dependency_overrides[solve.current_user] = lambda: user
    return TestClient(app), deps


def script() -> FakeLLM:
    return calc(
        ("chat_tools", tool("run_python", code="result = {}")),
        ("chat_json", {"answer_md": "X = 0.6667"}),
    )


def test_full_solve_over_http() -> None:
    http, _ = client_for(script())
    start = http.post("/api/v1/solve", json={"question": "Find X"})
    assert start.status_code == 200
    sid, step = start.json()["solve_id"], start.json()["step"]
    assert step["type"] == "run_python"
    assert http.get(f"/api/v1/solve/{sid}").json() == {"step": step}
    body = {"stdout": "", "result": GOOD, "figures": [], "error": None, "ms": 12}
    final = http.post(f"/api/v1/solve/{sid}/result", json=body).json()["step"]
    assert final["type"] == "final" and final["confidence"] == "high"


def test_unauthenticated_by_default() -> None:
    app = FastAPI()
    app.include_router(solve.router)
    app.dependency_overrides[solve.get_deps] = lambda: None
    r = TestClient(app).post("/api/v1/solve", json={"question": "q"})
    assert r.status_code == 401


def test_unknown_or_foreign_solve_is_404() -> None:
    http, _ = client_for(script())
    sid = http.post("/api/v1/solve", json={"question": "q"}).json()["solve_id"]
    other = TestClient(http.app)
    other.app.dependency_overrides[solve.current_user] = lambda: "intruder"  # type: ignore[attr-defined]
    body = {"result": GOOD}
    assert other.post(f"/api/v1/solve/{sid}/result", json=body).status_code == 404
    assert other.get(f"/api/v1/solve/{sid}").status_code == 404
    assert other.get("/api/v1/solve/nope").status_code == 404


def test_body_limits() -> None:
    http, _ = client_for(script())
    sid = http.post("/api/v1/solve", json={"question": "q"}).json()["solve_id"]
    huge = json.dumps({"stdout": "x" * (3 * 1024 * 1024 + 1)})
    r = http.post(
        f"/api/v1/solve/{sid}/result",
        content=huge,
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413
    bad = http.post(
        f"/api/v1/solve/{sid}/result",
        content=b"not json",
        headers={"content-type": "application/json"},
    )
    assert bad.status_code == 422


def test_question_is_validated() -> None:
    http, _ = client_for(script())
    assert http.post("/api/v1/solve", json={"question": ""}).status_code == 422
    r: Any = http.post("/api/v1/solve", json={"question": "x" * 4001})
    assert r.status_code == 422
