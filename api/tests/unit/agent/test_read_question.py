"""C2 tests: image/PDF preparation and the vision read, with a fake client."""

import asyncio
import base64
import functools
import io
from collections.abc import Callable, Coroutine
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pytest
from PIL import Image, ImageDraw

from app.agent import read_question as rq
from app.agent.read_question import (
    PROMPT,
    QuestionRead,
    UnsupportedUpload,
    prepare_image,
    prepare_image_async,
    read_question,
)
from app.llm.client import LLMResult
from app.llm.errors import DeadlineExceeded, ModelUnavailable


def sync(fn: Callable[..., Coroutine[Any, Any, None]]) -> Callable[..., None]:
    """Run an async test with asyncio.run (no pytest plugin needed)."""

    @functools.wraps(fn)
    def wrapper(*a: Any, **k: Any) -> None:
        asyncio.run(fn(*a, **k))

    return wrapper


def _encode(img: Image.Image, fmt: str, **kw: Any) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def _drawing(size: tuple[int, int], mode: str = "RGB") -> Image.Image:
    img = Image.new(mode, size, "white")
    ImageDraw.Draw(img).text((10, 10), "F = m a = 4.5 N", fill="black")
    return img


def _decode(url: str) -> Image.Image:
    prefix = "data:image/jpeg;base64,"
    assert url.startswith(prefix)
    img = Image.open(io.BytesIO(base64.b64decode(url[len(prefix) :])))
    assert img.format == "JPEG"
    return img


def _pdf(sizes: list[tuple[float, float]]) -> bytes:
    doc = pdfium.PdfDocument.new()
    for w, h in sizes:
        doc.new_page(w, h)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("fmt", "mime"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_image_formats_become_jpeg(fmt: str, mime: str) -> None:
    out = _decode(prepare_image(_encode(_drawing((800, 600)), fmt), mime))
    assert out.size == (800, 600)  # not upscaled


def test_large_image_is_capped_at_1600() -> None:
    out = _decode(prepare_image(_encode(_drawing((3200, 1200)), "PNG"), "image/png"))
    assert out.size == (1600, 600)


def test_tall_image_is_capped_at_1600() -> None:
    out = _decode(prepare_image(_encode(_drawing((1000, 4000)), "PNG"), "image/png"))
    assert out.size == (400, 1600)


def test_exif_orientation_is_applied() -> None:
    img = _drawing((400, 200))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    out = _decode(prepare_image(_encode(img, "JPEG", exif=exif), "image/jpeg"))
    assert out.size == (200, 400)


def test_rgba_is_flattened_on_white() -> None:
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))  # fully transparent
    out = _decode(prepare_image(_encode(img, "PNG"), "image/png"))
    assert out.mode == "RGB"
    r, g, b = out.getpixel((25, 25))  # type: ignore[misc]
    assert min(r, g, b) >= 250


def test_pdf_pages_render_at_170_dpi() -> None:
    data = _pdf([(200, 100), (300, 150)])
    p1 = _decode(prepare_image(data, "application/pdf"))
    p2 = _decode(prepare_image(data, "application/pdf", page=2))
    scale = 170 / 72
    assert abs(p1.width - 200 * scale) <= 2
    assert abs(p1.height - 100 * scale) <= 2
    assert abs(p2.width - 300 * scale) <= 2
    assert abs(p2.height - 150 * scale) <= 2


def test_large_pdf_page_is_capped() -> None:
    out = _decode(prepare_image(_pdf([(842, 595)]), "application/pdf"))
    assert max(out.size) == 1600


@pytest.mark.parametrize("page", [0, 3, -1])
def test_pdf_page_out_of_range(page: int) -> None:
    with pytest.raises(UnsupportedUpload, match="page"):
        prepare_image(_pdf([(200, 100), (200, 100)]), "application/pdf", page=page)


@pytest.mark.parametrize("mime", ["image/heic", "text/plain", "image/gif", ""])
def test_unsupported_mime(mime: str) -> None:
    with pytest.raises(UnsupportedUpload, match="type"):
        prepare_image(b"whatever", mime)


def test_unsupported_upload_is_value_error() -> None:
    assert issubclass(UnsupportedUpload, ValueError)


def test_oversized_input() -> None:
    with pytest.raises(UnsupportedUpload, match="15 MB"):
        prepare_image(b"\0" * (15 * 1024 * 1024 + 1), "image/png")


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "application/pdf"])
def test_corrupt_bytes(mime: str) -> None:
    with pytest.raises(UnsupportedUpload):
        prepare_image(b"not really a file", mime)


def test_decompression_bomb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rq, "MAX_PIXELS", 1000)
    with pytest.raises(UnsupportedUpload):
        prepare_image(_encode(_drawing((100, 100)), "PNG"), "image/png")


@sync
async def test_prepare_image_async() -> None:
    data = _encode(_drawing((300, 200)), "PNG")
    assert await prepare_image_async(data, "image/png") == prepare_image(
        data, "image/png"
    )


class FakeClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[str, str, float | None, str | None]] = []

    async def vision(
        self,
        image_url: str,
        prompt: str,
        *,
        deadline: float | None = None,
        solve_id: str | None = None,
    ) -> LLMResult:
        self.calls.append((image_url, prompt, deadline, solve_id))
        return LLMResult(
            text=self.text,
            reasoning=None,
            tool_calls=[],
            model_id="test/vision",
            role="vision",
            cost_usd=0.0,
            attempts=1,
        )


PNG = _encode(_drawing((300, 200)), "PNG")
REPLY = (
    '{"text": "Find F if m = 1.5 kg and a = 3 m/s^2.", "latex": "F = m a", '
    '"figure_description": "", "confidence": "high"}'
)


@sync
async def test_valid_json_reply() -> None:
    client = FakeClient(REPLY)
    result = await read_question(client, PNG, "image/png")
    assert result == QuestionRead(
        text="Find F if m = 1.5 kg and a = 3 m/s^2.",
        latex="F = m a",
        figure_description="",
        confidence="high",
    )
    assert len(client.calls) == 1
    _decode(client.calls[0][0])


@sync
async def test_fenced_json_reply() -> None:
    client = FakeClient(f"Here you go:\n```json\n{REPLY}\n```")
    result = await read_question(client, PNG, "image/png")
    assert result.confidence == "high"
    assert result.latex == "F = m a"


@sync
async def test_reply_after_stripped_think_block() -> None:
    # LLMClient already strips <think> blocks; the leftover text has leading blanks.
    client = FakeClient("\n\n" + REPLY)
    result = await read_question(client, PNG, "image/png")
    assert result.text.startswith("Find F")


@pytest.mark.parametrize(
    "bad",
    [
        "Find F if m = 1.5 kg.",
        '{"text": "only text"}',
        REPLY.replace('"high"', '"certain"'),
        REPLY.replace("}", ', "extra": 1}'),
    ],
)
@sync
async def test_unparseable_reply_falls_back(bad: str) -> None:
    client = FakeClient(f"  {bad}\n")
    result = await read_question(client, PNG, "image/png")
    assert result == QuestionRead(
        text=bad, latex="", figure_description="", confidence="low"
    )
    assert len(client.calls) == 1  # never asks the model again


@pytest.mark.parametrize("empty", ["", "   \n"])
@sync
async def test_empty_reply_is_model_unavailable(empty: str) -> None:
    with pytest.raises(ModelUnavailable):
        await read_question(FakeClient(empty), PNG, "image/png")


@sync
async def test_deadline_and_solve_id_pass_through() -> None:
    client = FakeClient(REPLY)
    await read_question(
        client,
        PNG,
        "image/png",
        deadline=123.5,
        solve_id="s-1",
    )
    _, _, deadline, solve_id = client.calls[0]
    assert (deadline, solve_id) == (123.5, "s-1")


@sync
async def test_pdf_page_is_used() -> None:
    client = FakeClient(REPLY)
    data = _pdf([(200, 100), (300, 150)])
    await read_question(client, data, "application/pdf", page=2)
    assert abs(_decode(client.calls[0][0]).width - 300 * 170 / 72) <= 2


@sync
async def test_client_errors_propagate() -> None:
    class Failing(FakeClient):
        async def vision(self, *a: Any, **k: Any) -> LLMResult:
            raise DeadlineExceeded("late")

    with pytest.raises(DeadlineExceeded):
        await read_question(Failing(""), PNG, "image/png")


@sync
async def test_bad_upload_never_calls_model() -> None:
    client = FakeClient(REPLY)
    with pytest.raises(UnsupportedUpload):
        await read_question(client, b"x", "image/heic")
    assert client.calls == []


def test_prompt_says_transcribe_only() -> None:
    low = PROMPT.lower()
    assert "do not solve" in low
    assert "exactly as written" in low
    assert "latex" in low
    assert "json" in low
    for key in ("text", "latex", "figure_description", "confidence"):
        assert key in PROMPT
