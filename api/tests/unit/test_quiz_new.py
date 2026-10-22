"""T1: POST /api/v1/quizzes with a fake model, fake vision, fake storage and a fake engine."""

import io
import re
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.agent.quiz import BlankItem, parse_quiz
from app.llm.client import LLMResult
from app.llm.errors import BudgetExceeded, ModelUnavailable
from app.main import app
from app.routers import checkins, prep, quiz_new, solve, uploads
from tests.unit.conftest import MemoryStorage

NOTES = "notes-" + "a" * 32
PHOTO = "question-" + "b" * 32


def mcq(i: int) -> dict[str, Any]:
    return {"type": "mcq", "topic": "CSTR", "stem": f"Question {i}?", "options": ["a", "b", "c", "d"],
            "correct_index": 0, "misconceptions": {"1": "m", "2": "m", "3": "m"}, "explanation": "e"}


def blank(i: int) -> dict[str, Any]:
    return {"type": "blank", "topic": "CSTR", "stem": f"A CSTR is ____ number {i}.", "answers": ["well mixed"],
            "explanation": "e"}


class FakeLLM:
    def __init__(self, items: list[dict[str, Any]], vision_text: str = "scanned notes on reactors",
                 error: Exception | None = None) -> None:
        self.items, self.error, self.vision_text = items, error, vision_text
        self.prompts: list[list[Any]] = []
        self.vision_calls = self.served = 0

    async def chat_json(self, role: str, messages: list[Any], schema: type[Any], **_: Any) -> tuple[Any, Any]:
        self.prompts.append(messages)
        if self.error:
            raise self.error
        size = int(re.search(r"n_items: (\d+)", messages[1]["content"])[1])  # type: ignore[index]
        start, self.served = self.served, self.served + size  # each batch gets the next slice
        return schema(title="Quiz", items=self.items[start : start + size]), None

    async def vision(self, image_url: str, prompt: str, **_: Any) -> LLMResult:
        self.vision_calls += 1
        text = (f'{{"text": "{self.vision_text} {self.vision_calls}", "latex": "", '
                '"figure_description": "", "confidence": "high"}')
        return LLMResult(text=text, reasoning=None, tool_calls=[], model_id="v", role="vision",
                         cost_usd=0.0, attempts=1)


class Conn:
    def __init__(self, sink: list[Any]) -> None:
        self.sink = sink

    async def execute(self, stmt: Any) -> None:
        self.sink.append(stmt.compile().params)


class Engine:
    def __init__(self) -> None:
        self.rows: list[Any] = []

    def begin(self) -> Any:
        @asynccontextmanager
        async def cm() -> Any:
            yield Conn(self.rows)
        return cm()


def text_pdf(text: str) -> bytes:
    """Minimal hand-written one-page PDF with a Helvetica text block (no parens/backslashes in text)."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) > 70:
            lines.append(cur)
            cur = ""
        cur += w + " "
    lines.append(cur)
    stream = b"BT /F1 10 Tf 12 780 Td 12 TL " + b" T* ".join(b"(%s) Tj" % ln.encode() for ln in lines) + b" ET"
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[4 0 R]/Count 1>>",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 3 0 R>>>>/Contents 5 0 R>>",
            b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream"]
    out, offs = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)


def blank_pdf(pages: int) -> bytes:
    """Pages with no text layer, like a scan."""
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused@localhost/x")
    state: dict[str, Any] = {"llm": FakeLLM([mcq(i) for i in range(5)]), "engine": Engine(), "storage": MemoryStorage()}
    saved = dict(app.dependency_overrides)
    app.dependency_overrides |= {
        solve.current_user: lambda: "u1", checkins.get_engine: lambda: state["engine"],
        prep.get_llm: lambda: state["llm"], uploads.get_storage_opt: lambda: state["storage"]}
    try:
        yield state
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def post(body: dict[str, Any]) -> Any:
    return TestClient(app).post("/api/v1/quizzes", json=body)


def test_topic_only_defaults(env: dict[str, Any]) -> None:
    r = post({"topic": "CSTR"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["topic"] == "CSTR" and b["marks_per_q"] == 1 and len(b["items"]) == 5
    assert b["total_marks"] == 5 and b["suggested_minutes"] == 10 and b["title"] == "Quiz"
    stored = env["engine"].rows
    assert len(stored) == 1 and stored[0]["id"] == b["id"] and stored[0]["user_id"] == "u1"
    assert stored[0]["quiz"]["items"] == b["items"] and stored[0]["quiz"]["marks_per_q"] == 1
    assert env["llm"].vision_calls == 0


def test_marks_minutes_and_kinds_reach_the_generator(env: dict[str, Any]) -> None:
    env["llm"] = FakeLLM([mcq(0), blank(1), mcq(2), blank(3)])
    b = post({"topic": "CSTR", "kinds": "mixed", "marks_per_q": 4, "n_items": 4}).json()
    assert b["total_marks"] == 16 and b["suggested_minutes"] == 12
    assert [i["type"] for i in b["items"]] == ["mcq", "blank", "mcq", "blank"]
    assert "fill-in-the-blank" in env["llm"].prompts[0][0]["content"]


def test_pdf_with_text_layer_is_notes_and_skips_vision(env: dict[str, Any]) -> None:
    data = text_pdf("Residence time of a CSTR equals volume over flow rate. " * 8)
    env["storage"].objs[f"u1/{NOTES}"] = (data, "application/pdf")
    assert post({"topic": "CSTR", "upload_id": NOTES}).status_code == 200
    assert "Residence time of a CSTR" in env["llm"].prompts[0][1]["content"]
    assert env["llm"].vision_calls == 0


def test_scanned_pdf_uses_vision_on_at_most_3_pages(env: dict[str, Any]) -> None:
    env["storage"].objs[f"u1/{NOTES}"] = (blank_pdf(5), "application/pdf")
    assert post({"topic": "CSTR", "upload_id": NOTES}).status_code == 200
    assert env["llm"].vision_calls == 3
    assert "scanned notes on reactors" in env["llm"].prompts[0][1]["content"]


def test_image_uses_vision(env: dict[str, Any]) -> None:
    env["storage"].objs[f"u1/{PHOTO}"] = (png(), "image/png")
    assert post({"topic": "CSTR", "upload_id": PHOTO}).status_code == 200
    assert env["llm"].vision_calls == 1


def test_no_vision_client_gives_422_for_a_scan(env: dict[str, Any]) -> None:
    class NoVision:
        async def chat_json(self, *a: Any, **k: Any) -> Any:
            raise AssertionError("must not be called")

    env["llm"] = NoVision()
    env["storage"].objs[f"u1/{NOTES}"] = (blank_pdf(1), "application/pdf")
    assert post({"topic": "CSTR", "upload_id": NOTES}).status_code == 422


def test_errors(env: dict[str, Any]) -> None:
    assert post({"topic": "CSTR", "upload_id": NOTES}).status_code == 404  # missing
    assert post({"topic": "CSTR", "upload_id": "../x"}).status_code == 404  # bad id
    env["storage"].objs[f"other/{NOTES}"] = (png(), "image/png")
    assert post({"topic": "CSTR", "upload_id": NOTES}).status_code == 404  # another student's
    for bad in ({}, {"topic": ""}, {"topic": "x" * 81}, {"topic": "a", "n_items": 2}, {"topic": "a", "n_items": 21},
                {"topic": "a", "kinds": "essay"}, {"topic": "a", "marks_per_q": 3}, {"topic": "a", "extra": 1}):
        assert post(bad).status_code == 422, bad
    env["llm"] = FakeLLM([])  # no usable questions (one is enough now: batches ask for 2)
    assert post({"topic": "CSTR"}).status_code == 502
    env["llm"] = FakeLLM([], error=ModelUnavailable("down"))
    assert post({"topic": "CSTR"}).status_code == 502
    env["llm"] = FakeLLM([], error=BudgetExceeded("cap"))
    assert post({"topic": "CSTR"}).status_code == 429
    assert env["engine"].rows == []  # nothing stored on any failure
    env["llm"] = None
    r = post({"topic": "CSTR"})
    assert r.status_code == 503 and r.json() == {"detail": "quiz not available"}


def test_needs_database_and_sign_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert post({"topic": "CSTR"}).status_code == 503
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused@localhost/x")
    assert post({"topic": "CSTR"}).status_code == 401
    assert quiz_new.router is not None


def test_blank_item_schema() -> None:
    ok = blank(1)
    assert isinstance(parse_quiz({"title": "t", "items": [ok]}).items[0], BlankItem)
    for patch in ({"stem": "no gap here"}, {"answers": []}, {"answers": ["x"] * 6}, {"answers": [""]},
                  {"answers": ["x" * 61]}, {"extra": 1}):
        with pytest.raises(ValidationError):
            parse_quiz({"title": "t", "items": [{**ok, **patch}]})


def test_generate_quiz_default_kinds_is_the_old_behaviour() -> None:
    import asyncio

    from app.agent.quiz_gen import generate_quiz

    llm = FakeLLM([mcq(i) for i in range(3)])
    asyncio.run(generate_quiz(llm, "CSTR", 3))
    system = llm.prompts[0][0]["content"]
    assert 'Do not use the type "blank".' in system and "fill-in-the-blank" not in system
    assert "Use only" not in system and "only multiple choice" not in system


class BatchLLM(FakeLLM):
    """Each call returns as many new stems as it was asked for (n_items in the prompt), or fails from call
    `fail_from` on. dup=True: every call returns the same stems. short: return only this many per call."""

    def __init__(self, fail_from: int = 99, dup: bool = False, short: int | None = None) -> None:
        super().__init__([])
        self.fail_from, self.dup, self.short, self.next = fail_from, dup, short, 0
        self.kwargs: list[dict[str, Any]] = []

    async def chat_json(self, role: str, messages: list[Any], schema: type[Any], **kw: Any) -> tuple[Any, Any]:
        n = len(self.prompts)
        self.prompts.append(messages)
        self.kwargs.append(kw)
        if n >= self.fail_from:
            raise ModelUnavailable("down")
        size = int(re.search(r"n_items: (\d+)", messages[1]["content"])[1])  # type: ignore[index]
        size = min(size, self.short or size)
        start = 0 if self.dup else self.next
        self.next += size
        return schema(title=f"Quiz {n}", items=[mcq(start + i) for i in range(size)]), None

    def sizes(self) -> list[int]:
        return [int(re.search(r"n_items: (\d+)", p[1]["content"])[1]) for p in self.prompts]  # type: ignore[index]


@pytest.mark.parametrize(("n", "sizes"), [
    (5, [2, 2, 2]), (10, [2] * 6), (15, [3, 3] + [2] * 6), (20, [3] * 8)])
def test_batches_of_two_with_global_over_ask(env: dict[str, Any], n: int, sizes: list[int]) -> None:
    env["llm"] = llm = BatchLLM()
    b = post({"topic": "CSTR", "n_items": n}).json()
    assert llm.sizes() == sizes and sum(sizes) == n + -(-n // 5) and len(sizes) <= 8
    assert len(b["items"]) == n and b["total_marks"] == n and b["title"] == "Quiz 0"


def test_each_batch_gets_a_focus_and_a_deadline_and_min_items_is_one(env: dict[str, Any]) -> None:
    env["llm"] = llm = BatchLLM(short=1)  # one valid item per batch must not trigger a serial retry
    before = time.monotonic()
    post({"topic": "CSTR", "n_items": 10})
    assert len(llm.prompts) == 6
    focus = [p[1]["content"].split("focus: ")[1].split("\n")[0] for p in llm.prompts]
    assert len(set(focus[:4])) == 4 and focus[4] == focus[0]
    assert all(before + 70 < k["deadline"] < time.monotonic() + 81 for k in llm.kwargs)


def test_duplicates_across_batches_are_dropped(env: dict[str, Any]) -> None:
    env["llm"] = BatchLLM(dup=True)
    stems = [i["stem"] for i in post({"topic": "CSTR", "n_items": 20}).json()["items"]]
    assert len(stems) == 3 == len(set(stems))


def test_failing_later_batches_return_the_first(env: dict[str, Any]) -> None:
    env["llm"] = BatchLLM(fail_from=1)
    r = post({"topic": "CSTR", "n_items": 20})
    assert r.status_code == 200 and len(r.json()["items"]) == 3
    env["llm"] = BatchLLM(fail_from=0)  # the first batch failing is still a 502
    assert post({"topic": "CSTR", "n_items": 20}).status_code == 502


def put_read(env: dict[str, Any], data: bytes, mime: str) -> None:
    env["storage"].objs[f"u1/{PHOTO}"] = (data, mime)


def read() -> Any:
    return TestClient(app).post(f"/api/v1/uploads/{PHOTO}/read")


EMPTY = {"text": "", "latex": "", "figure_description": "", "confidence": "low"}


def test_read_text_pdf_needs_no_model(env: dict[str, Any]) -> None:
    put_read(env, text_pdf("A heat exchanger has area A. Find the heat duty. " * 8), "application/pdf")
    b = read().json()
    assert "heat exchanger" in b["text"] and b["confidence"] == "medium" and b["latex"] == ""
    assert env["llm"].vision_calls == 0


def test_read_scan_joins_text_latex_and_figure(env: dict[str, Any]) -> None:
    llm = env["llm"]

    async def vision(image_url: str, prompt: str, **_: Any) -> LLMResult:
        llm.vision_calls += 1
        body = ('{"text": "Find Q.", "latex": "Q = U A \\\\Delta T", "figure_description": "a pipe", '
                '"confidence": "high"}')
        return LLMResult(text=body, reasoning=None, tool_calls=[], model_id="v", role="vision",
                         cost_usd=0.0, attempts=1)

    llm.vision = vision
    put_read(env, blank_pdf(2), "application/pdf")
    r = read()
    assert r.status_code == 200 and llm.vision_calls == 1  # page 1 only
    b = r.json()
    assert b["text"] == "Find Q.\n\n$$\nQ = U A \\Delta T\n$$\n\nFigure: a pipe" and b["confidence"] == "high"


def test_read_photo_uses_vision(env: dict[str, Any]) -> None:
    put_read(env, png(), "image/png")
    assert "scanned notes" in read().json()["text"] and env["llm"].vision_calls == 1


def test_read_unreadable_or_empty_is_200_with_empty_text(env: dict[str, Any]) -> None:
    put_read(env, b"not an image", "image/png")
    r = read()
    assert r.status_code == 200 and r.json() == EMPTY
    put_read(env, png(), "image/png")
    env["llm"].vision_text = ""
    env["llm"].vision = lambda *a, **k: _empty_read()  # type: ignore[assignment]
    assert read().json() == EMPTY


async def _empty_read() -> LLMResult:
    body = '{"text": "", "latex": "", "figure_description": "", "confidence": "low"}'
    return LLMResult(text=body, reasoning=None, tool_calls=[], model_id="v", role="vision",
                     cost_usd=0.0, attempts=1)


def test_read_errors(env: dict[str, Any]) -> None:
    assert read().status_code == 404
    put_read(env, png(), "image/png")
    for err, code in ((BudgetExceeded("cap"), 429), (ModelUnavailable("down"), 502)):
        async def boom(*a: Any, _e: Exception = err, **k: Any) -> LLMResult:
            raise _e

        env["llm"].vision = boom
        assert read().status_code == code
    env["storage"].fail = True
    assert read().status_code == 502
    env["storage"].fail = False
    env["llm"] = None
    assert read().status_code == 503
    env["llm"], env["storage"] = FakeLLM([]), None
    assert read().status_code == 503


def test_read_trims_to_4000_at_a_line_boundary(env: dict[str, Any]) -> None:
    llm = env["llm"]
    long = "\\n".join(f"line {i:04d} " + "x" * 90 for i in range(60))  # 6000 chars

    async def vision(*a: Any, **k: Any) -> LLMResult:
        body = '{"text": "' + long + '", "latex": "", "figure_description": "", "confidence": "high"}'
        return LLMResult(text=body, reasoning=None, tool_calls=[], model_id="v", role="vision",
                         cost_usd=0.0, attempts=1)

    llm.vision = vision
    put_read(env, png(), "image/png")
    text = read().json()["text"]
    assert 3800 < len(text) <= 4000 and text.splitlines()[-1].endswith("x" * 90)
