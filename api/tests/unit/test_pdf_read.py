import httpx
import pytest
from fastapi import FastAPI

from app.routers import pdf, uploads
from tests.integration.test_notes import make_pdf

pytestmark = pytest.mark.anyio


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(pdf.router)
    a.dependency_overrides[uploads.current_user] = lambda: "A"
    return a


async def post(a: FastAPI, data: bytes) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=a), base_url="http://t") as c:
        return await c.post("/api/v1/pdf/read", files={"file": ("x.pdf", data, "application/pdf")})


async def test_30_page_pdf_counts_pages_and_words(app: FastAPI) -> None:
    pages = [f"Page {i} heat exchanger design notes" for i in range(1, 30)] + [""]  # last page blank
    r = await post(app, make_pdf(pages))
    assert r.status_code == 200
    body = r.json()
    assert body["pages"] == 30
    assert body["words"] == 29 * 6
    assert body["text"][0] == "Page 1 heat exchanger design notes" and body["text"][29] == ""


async def test_not_a_pdf_or_broken_is_415_and_signed_out_is_401(app: FastAPI) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert (await post(app, png)).status_code == 415
    assert (await post(app, b"%PDF-1.4 broken")).status_code == 415
    app.dependency_overrides.clear()
    assert (await post(app, make_pdf(["x"]))).status_code == 401


async def test_size_cap_413(app: FastAPI) -> None:
    assert (await post(app, b"%PDF-" + b"0" * (uploads.MAX_BYTES + 1))).status_code == 413


def test_read_caps_pages_but_reports_the_true_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "MAX_PAGES", 3)
    got = pdf.read(make_pdf(["a b", "c", "d", "e f g"]))
    assert got == {"pages": 4, "words": 4, "text": ["a b", "c", "d"]}


def test_line_breaks_are_kept_for_question_splitting() -> None:
    q = "Q1. Derive the design equation of a CSTR and state every assumption you make clearly (10 marks)"
    got = pdf.read(make_pdf([q]))["text"][0]
    assert "\n" in got and got.replace("\n", " ").split() == q.split()


def test_every_pdfium_user_shares_one_lock() -> None:
    from app import notes, pdfium_lock
    from app.agent import read_question
    for f in (pdf.read, notes.pdf_pages, read_question._render_pdf_page):
        assert f.__wrapped__ is not None  # type: ignore[attr-defined]
    with pdfium_lock._LOCK:  # held elsewhere: a reader in another thread must wait
        import threading
        t = threading.Thread(target=pdf.read, args=(make_pdf(["x"]),))
        t.start()
        t.join(0.3)
        assert t.is_alive()
    t.join(5)
    assert not t.is_alive()
