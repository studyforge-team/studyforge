import pytest
from fastapi.testclient import TestClient

from app import prep, wiring
from app.main import app


def test_links_of() -> None:
    nid = "notes-" + "a" * 32
    assert prep.links_of(f"notes:{nid}#page=3") == {"upload_id": nid, "page": 3}
    for bad in (None, "", "textbook ch. 4", f"notes:{nid}#page=x", f"notes:{nid}#page=3 extra", "notes:../x#page=1"):
        assert prep.links_of(bad) is None


def test_keys_are_task_hashes() -> None:
    assert prep.KEY.fullmatch("0123456789abcdef")
    good = "0123456789abcdef"
    for bad in (good.upper(), good[:-1], "../etc/passwd", good + "0"):
        assert not prep.KEY.fullmatch(bad)


def test_model_is_optional_for_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert wiring.prep_llm() is None  # no database or no key: None, never an exception


def test_database_and_sign_in_required(monkeypatch: pytest.MonkeyPatch) -> None:
    c = TestClient(app)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert c.get("/api/v1/prep/0123456789abcdef").status_code == 503
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused@localhost/x")  # never connected: auth fails first
    assert c.get("/api/v1/prep/0123456789abcdef").status_code == 401


@pytest.mark.anyio
async def test_build_asks_for_the_most_and_needs_five(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent.quiz import Quiz
    from app.agent.quiz_gen import MAX_ITEMS

    seen: dict[str, object] = {}

    async def fake(llm: object, topic: str, n: int, **kw: object) -> Quiz:
        seen.update(n=n, **kw)
        return Quiz.model_construct(title="t", items=[])

    async def hits(*_: object, **__: object) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(prep, "generate_quiz", fake)
    monkeypatch.setattr(prep.notes, "search", hits)
    with pytest.raises(prep.QuizGenerationFailed):
        await prep.build(None, object(), "u", "k", "CRE")  # type: ignore[arg-type]
    assert seen["n"] == MAX_ITEMS and seen["min_items"] == prep.N_QUESTIONS == 5


def test_common_words_never_link() -> None:
    assert prep._words("What is the heat calculate value of THIS exchanger?") == {"heat", "exchanger"}


@pytest.mark.anyio
async def test_budget_exceeded_never_starts_the_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm.errors import BudgetExceeded

    async def task(*_: object) -> dict[str, str]:
        return {"title": "CRE", "deadline_utc": ""}

    async def none(*_: object) -> None:
        return None

    async def over(*_: object) -> None:
        raise BudgetExceeded("daily cap")

    monkeypatch.setattr(prep, "find_task", task)
    monkeypatch.setattr(prep, "stored", none)
    monkeypatch.setattr(prep, "build", over)
    for _ in range(2):  # the second open is still "budget", not "cooling down"
        with pytest.raises(BudgetExceeded):
            await prep.get_or_build(None, object(), "u", "0123456789abcdef")  # type: ignore[arg-type]
