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
    for bad in ("0123456789ABCDEF", "0123456789abcde", "../etc/passwd", "0123456789abcdef0"):
        assert not prep.KEY.fullmatch(bad)


def test_model_is_optional_for_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert wiring.prep_llm() is None  # no database or no key: None, never an exception


def test_sign_in_and_database_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    c = TestClient(app)
    assert c.get("/api/v1/prep/0123456789abcdef").status_code in (401, 503)  # no token, no database: never 200
