from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from test_loop import USER, FakeLLM, deps, run
from test_solve_routes import script

from app import spend
from app.agent import loop
from app.agent.state import SolveState
from app.llm.errors import BudgetExceeded
from app.routers import solve

PREFIX = "Today's AI limit is reached, so here is a saved answer to the same question:\n\n"
SAVED = {"type": "final", "answer_md": "X = 0.6667", "numbers": {"x": 0.6667},
         "figures": [], "sources": [], "confidence": "high"}


@pytest.mark.parametrize("xff,peer,want", [
    ("1.2.3.4", "9.9.9.9", "1.2.3.4"),
    ("6.6.6.6, 1.2.3.4", "9.9.9.9", "1.2.3.4"),  # leftmost is client-supplied: rightmost wins
    ("6.6.6.6 ,  1.2.3.4  ", None, "1.2.3.4"),
    ("1.2.3.4, , ", "9.9.9.9", "1.2.3.4"),
    ("1.2.3.4, 10.29.8.12", "10.0.0.1", "1.2.3.4"),  # Render's internal hop is skipped
    ("6.6.6.6, 1.2.3.4, 10.29.8.12, 10.0.0.7", None, "1.2.3.4"),  # still never the spoofed left
    ("10.1.1.1, 1.2.3.4", None, "1.2.3.4"),  # a spoofed private entry on the left changes nothing
    ("10.29.8.12", "9.9.9.9", "10.29.8.12"),  # only internal hops: rightmost, as before
    ("1.2.3.4, 100.64.3.9", None, "1.2.3.4"),  # CGNAT proxy range is internal too
    ("1.2.3.4, 172.71.198.58, 10.29.8.12", None, "1.2.3.4"),  # Cloudflare edge skipped (26 Oct log)
    ("6.6.6.6, 1.2.3.4, 2606:4700::1", None, "1.2.3.4"),  # Cloudflare IPv6 edge, spoofed left ignored
    ("172.71.198.58", "9.9.9.9", "172.71.198.58"),  # only proxy hops: rightmost, as before
    ("", "9.9.9.9", "9.9.9.9"),
    (None, "9.9.9.9", "9.9.9.9"),
    (None, None, None),
])
def test_client_ip(xff: str | None, peer: str | None, want: str | None) -> None:
    assert spend.client_ip(xff, peer) == want


def test_caps_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("SPEND_CAP_USD", "DAILY_GLOBAL_USD", "DAILY_USER_USD", "DAILY_IP_USD"):
        monkeypatch.delenv(k, raising=False)
    assert spend.Caps.from_env() == spend.Caps()
    monkeypatch.setenv("DAILY_USER_USD", "")
    assert spend.Caps.from_env().user is None
    monkeypatch.setenv("SPEND_CAP_USD", "12.5")
    monkeypatch.setenv("DAILY_IP_USD", "0.1")
    assert spend.Caps.from_env() == spend.Caps(total=12.5, ip=0.1)
    monkeypatch.setenv("DAILY_GLOBAL_USD", "abc")
    with pytest.raises(ValueError):
        spend.Caps.from_env()


def capped_deps(seed: SolveState | None) -> loop.Deps:
    d = deps(FakeLLM(("chat_json", BudgetExceeded("cap"))))
    if seed:
        run(d.store.save(seed))
    return d


def test_cap_hit_serves_cached_answer() -> None:  # the T7 done-when
    seed = SolveState(id="old", user_id="other", question="Find   X", status="done", last_step=SAVED)
    d = capped_deps(seed)
    sid, step = run(loop.start("find x", d, user_id=USER))
    assert step["type"] == "final" and step["answer_md"] == PREFIX + "X = 0.6667"
    assert step["numbers"] == {"x": 0.6667}
    got = run(d.store.get(sid))
    assert got is not None and got.status == "done" and "cached" in got.flags
    # a cached copy must not itself be served as a cache source
    assert run(d.store.cached("find x")) == SAVED


def test_cap_hit_cached_answer_is_at_most_medium() -> None:
    seed = SolveState(id="old", user_id="other", question="find x", status="done", last_step=SAVED)
    _, step = run(loop.start("find x", capped_deps(seed), user_id=USER))
    assert SAVED["confidence"] == "high" and step["confidence"] == "medium"
    assert step["answer_md"].startswith(PREFIX)


def test_cap_hit_without_cache_says_so() -> None:
    flagged = SolveState(id="old", user_id="o", question="find x", status="done",
                         last_step=SAVED, flags=["limit_reached"])
    d = capped_deps(flagged)
    sid, step = run(loop.start("find x", d, user_id=USER))
    assert step["confidence"] == "low" and step["numbers"] == {}
    assert "can't solve a new question" in step["answer_md"]
    got = run(d.store.get(sid))
    assert got is not None and "spend_cap" in got.flags


def test_spend_context_sets_who(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[spend.Who] = []
    orig = loop.start

    async def spy(*a: Any, **kw: Any) -> Any:
        seen.append(spend.who.get())  # runs in the async route: the ContextVar must have arrived
        return await orig(*a, **kw)

    monkeypatch.setattr(loop, "start", spy)
    app = FastAPI()
    app.include_router(solve.router)
    app.dependency_overrides[solve.get_deps] = lambda: deps(script())

    def user(request: Request) -> str:  # stands in for auth.current_user (sync, threadpool)
        request.state.anon = request.headers.get("x-anon") == "1"
        return "u9"

    app.dependency_overrides[solve.current_user] = user
    http = TestClient(app)
    http.post("/api/v1/solve", json={"question": "Find X"},
              headers={"x-anon": "1", "x-forwarded-for": "6.6.6.6, 1.2.3.4"})
    http.post("/api/v1/solve", json={"question": "Find X"})
    assert seen[0] == spend.Who("u9", True, "1.2.3.4")
    assert seen[1].anon is False and seen[1].user_id == "u9"


def test_spend_context_without_anon_attr() -> None:
    # tests override current_user with a plain function that never sets request.state.anon
    app = FastAPI()
    app.include_router(solve.router)
    app.dependency_overrides[solve.get_deps] = lambda: deps(script())
    app.dependency_overrides[solve.current_user] = lambda: "u1"
    assert TestClient(app).post("/api/v1/solve", json={"question": "Find X"}).status_code == 200
