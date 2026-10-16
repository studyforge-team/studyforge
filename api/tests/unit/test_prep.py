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


def test_common_words_never_link() -> None:
    assert prep._words("What is the heat calculate value of THIS exchanger?") == {"heat", "exchanger"}
