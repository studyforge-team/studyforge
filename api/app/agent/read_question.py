"""C2: read a question from a photo or a scanned PDF page with the vision model.

The vision model only transcribes and describes; it never solves. Its output
ALWAYS goes to the student's confirm screen, where the student can edit it before
anything is solved, so a misread digit is caught by a person, not by the agent.
"""

import asyncio
import base64
import io
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict

from app.llm.client import LLMResult
from app.llm.errors import LLMError, ModelUnavailable
from app.llm.reasoning import extract_json
from app.pdfium_lock import one_at_a_time

MAX_INPUT_BYTES = 15 * 1024 * 1024
MAX_WIDTH = 1600
MAX_HEIGHT = 4000
MAX_SHRINK = 1.5  # a read shrunk more than this is capped at "medium" confidence
PDF_DPI = 200
MAX_PIXELS = 60_000_000  # decompression-bomb guard for uploaded images
JPEG_QUALITY = 85
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
PDF_MIME = "application/pdf"

PROMPT = """You are reading a photo or scan of an engineering exam or homework question.
Only transcribe and describe what is on the page. Do NOT solve the problem, do not \
give hints, and do not add facts that are not shown.
- Copy every number, unit and symbol exactly as written. Never round, fix or guess a \
value. If something is unreadable, write [unclear] in its place and lower your confidence.
- Never flatten a power or subscript: in "text" write 3.7×10^4, 2.4×10^-3, m^3, C_A0, \
never 3.7×104 or m3.
- Put mathematics in LaTeX in the "latex" field. Keep plain wording in "text".
- If there is a figure, graph, circuit or diagram, describe what it shows (labels, \
values, axes) in "figure_description". Use an empty string if there is none.
Reply with only a JSON object with exactly these four keys:
{"text": "<the question as plain text>", "latex": "<the maths in LaTeX, or empty>", \
"figure_description": "<description or empty>", "confidence": "high" | "medium" | "low"}"""


class UnsupportedUpload(ValueError):
    """The uploaded file cannot be read (type, size, page or contents)."""


class QuestionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    latex: str
    figure_description: str
    confidence: Literal["high", "medium", "low"]


class _Vision(Protocol):
    async def vision(
        self,
        image_url: str,
        prompt: str,
        *,
        deadline: float | None = None,
        solve_id: str | None = None,
    ) -> LLMResult: ...


def prepare_image(data: bytes, mime: str, page: int = 1) -> str:
    """Return a JPEG data URL (width <= 1600 px, height <= 4000 px) for an image or PDF page."""
    return prepare_image_shrink(data, mime, page)[0]


def prepare_image_shrink(data: bytes, mime: str, page: int = 1) -> tuple[str, float]:
    """prepare_image plus how much the image was shrunk (linear factor, 1.0 = not shrunk)."""
    if mime != PDF_MIME and mime not in IMAGE_MIMES:
        raise UnsupportedUpload(
            f"Unsupported file type '{mime}'. Upload a JPEG, PNG, WEBP or PDF."
        )
    if len(data) > MAX_INPUT_BYTES:
        raise UnsupportedUpload("File is too large. The limit is 15 MB.")
    try:
        img = _render_pdf_page(data, page) if mime == PDF_MIME else _open_image(data)
        img = _to_rgb(img)
        shrink = max(img.width / MAX_WIDTH, img.height / MAX_HEIGHT, 1.0)  # never upscales
        if shrink > 1:
            size = (max(1, round(img.width / shrink)), max(1, round(img.height / shrink)))
            img = img.resize(size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    except UnsupportedUpload:
        raise
    except Image.DecompressionBombError as err:
        raise UnsupportedUpload("Image has too many pixels.") from err
    except (OSError, ValueError, SyntaxError, pdfium.PdfiumError) as err:
        raise UnsupportedUpload("The file could not be read as an image.") from err
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}", shrink


async def prepare_image_async(data: bytes, mime: str, page: int = 1) -> str:
    """prepare_image on a worker thread so the event loop is not blocked."""
    return await asyncio.to_thread(prepare_image, data, mime, page)


def _open_image(data: bytes) -> Image.Image:
    old = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS // 2  # Pillow raises the error at twice this
    try:
        opened = Image.open(io.BytesIO(data))
        if opened.width * opened.height > MAX_PIXELS:
            raise UnsupportedUpload("Image has too many pixels.")
        img = ImageOps.exif_transpose(opened)
        img.load()
        return img
    finally:
        Image.MAX_IMAGE_PIXELS = old


@one_at_a_time
def _render_pdf_page(data: bytes, page: int) -> Image.Image:
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as err:
        raise UnsupportedUpload("The PDF could not be opened.") from err
    try:
        if not 1 <= page <= len(pdf):
            raise UnsupportedUpload(
                f"PDF page {page} does not exist (the file has {len(pdf)} pages)."
            )
        pdf_page = pdf[page - 1]
        width, height = pdf_page.get_size()
        scale = PDF_DPI / 72
        if width * scale * height * scale > MAX_PIXELS:
            raise UnsupportedUpload("PDF page is too large to render.")
        image: Image.Image = pdf_page.render(scale=scale).to_pil()
        return image
    finally:
        pdf.close()


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return img.convert("RGB")


async def read_question(
    client: _Vision,
    data: bytes,
    mime: str,
    page: int = 1,
    *,
    deadline: float | None = None,
    solve_id: str | None = None,
) -> QuestionRead:
    """Transcribe a question photo or PDF page; the result goes to the confirm screen.

    The student always reviews and may edit this text before it is solved.
    If the model's reply is not the expected JSON, the raw reply is returned with
    low confidence (no second model call) so the student can still fix it. An empty
    reply raises ModelUnavailable (the UI then offers typed input). Client errors
    (ModelUnavailable, DeadlineExceeded, LLMAuthError, BudgetExceeded) propagate.
    """
    image_url, shrink = await asyncio.to_thread(prepare_image_shrink, data, mime, page)
    result = await client.vision(
        image_url, PROMPT, deadline=deadline, solve_id=solve_id
    )
    raw = result.text.strip()
    if not raw:
        raise ModelUnavailable("the vision model returned an empty reply")
    try:
        payload: Any = extract_json(raw)
        read = QuestionRead.model_validate(payload)
    except ValueError:  # includes pydantic ValidationError
        return QuestionRead(text=raw, latex="", figure_description="", confidence="low")
    if shrink > MAX_SHRINK and read.confidence == "high":
        read.confidence = "medium"
    return read


def upload_reader(
    fetch: Callable[[str], Awaitable[tuple[bytes, str]]], client: _Vision
) -> Callable[[str], Awaitable[str]]:
    """The loop's read_upload: upload id -> text for the confirm screen.

    fetch(upload_id) returns (bytes, mime) from storage (C1). A photo that cannot be
    read gives "" so the student types the question instead of seeing an error."""

    async def read(upload_id: str) -> str:
        try:
            data, mime = await fetch(upload_id)
            q = await read_question(client, data, mime)
        except (LookupError, UnsupportedUpload, LLMError):
            return ""
        parts = [q.text]
        if q.latex and q.latex not in q.text:
            parts.append(f"$$\n{q.latex}\n$$")
        if q.figure_description:
            parts.append(f"Figure: {q.figure_description}")
        return "\n\n".join(x.strip() for x in parts if x.strip())

    return read
