"""Server-side caps on posted sandbox results, and the deterministic verify step.

Caps follow what the browser worker really sends: up to 4 figures as bare base64
PNG (<= 500 KB decoded each), stdout up to 64 KB plus a truncation note, and a
result capped at 16 KB in solve mode (a little slack for re-serialisation).
"""

import base64
import binascii
import json
import math
from dataclasses import dataclass, field
from typing import Any

from app.agent.steps import ResultBody

MAX_FIGURES = 4
MAX_FIGURE_BYTES = 500 * 1024
MAX_STDOUT = 64 * 1024
MAX_RESULT_JSON = 16 * 1024 + 1024
MAX_ERROR = 2000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
AGREE_REL = 1e-3  # the two methods must agree to 0.1 %
AGREE_ABS = 1e-12


@dataclass
class CleanResult:
    stdout: str
    result: Any
    error: str | None
    figures: list[str] = field(default_factory=list)  # data: URLs
    notes: list[str] = field(default_factory=list)  # what was cut, for the log


def clean(body: ResultBody) -> CleanResult:
    out = CleanResult(stdout=body.stdout, result=body.result, error=body.error)
    if len(out.stdout) > MAX_STDOUT:
        out.stdout = out.stdout[:MAX_STDOUT]
        out.notes.append("stdout truncated")
    if out.error is not None:
        out.error = out.error[-MAX_ERROR:]
    try:
        size = len(json.dumps(out.result, allow_nan=False))
    except (TypeError, ValueError):
        size = MAX_RESULT_JSON + 1
    if size > MAX_RESULT_JSON:
        out.result = None
        out.error = out.error or "result too large or not JSON"
    for raw in body.figures[:MAX_FIGURES]:
        try:
            png = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            out.notes.append("figure dropped: not base64")
            continue
        if not png.startswith(PNG_SIGNATURE) or len(png) > MAX_FIGURE_BYTES:
            out.notes.append("figure dropped: not a PNG or over 500 KB")
            continue
        out.figures.append("data:image/png;base64," + raw)
    if len(body.figures) > MAX_FIGURES:
        out.notes.append("extra figures dropped")
    return out


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str | None = None  # machine-friendly, shown to the model on repair
    disagree: bool = False  # both methods ran but gave different answers


def _number(node: Any) -> float | None:
    """A finite real number, else None (the worker turns sympy/Decimal into str)."""
    if isinstance(node, bool) or not isinstance(node, int | float):
        return None
    return float(node) if math.isfinite(node) else None


def _quantity(node: Any) -> tuple[float, str] | None:
    if not isinstance(node, dict):
        return None
    value, unit = _number(node.get("value")), node.get("unit")
    if value is None or not isinstance(unit, str) or not unit.strip():
        return None
    return value, unit.strip()


def verify(result: Any) -> Verdict:
    """Canonical result: {"answer": {value, unit}, "check": {value, unit, method},
    "values": {name: {value, unit}}}. Both methods must agree."""
    if not isinstance(result, dict):
        return Verdict(False, "result must be a dict")
    answer, check = _quantity(result.get("answer")), _quantity(result.get("check"))
    if answer is None:
        return Verdict(False, "result['answer'] must be {'value': float, 'unit': str}")
    if check is None:
        return Verdict(
            False, "result['check'] must be {'value': float, 'unit': str, ...}"
        )
    if answer[1] != check[1]:
        return Verdict(False, f"answer unit '{answer[1]}' != check unit '{check[1]}'")
    for name, node in (result.get("values") or {}).items():
        if _quantity(node) is None:
            return Verdict(False, f"result['values']['{name}'] must be {{value, unit}}")
    a, c = answer[0], check[0]
    if abs(a - c) > max(AGREE_REL * max(abs(a), abs(c)), AGREE_ABS):
        return Verdict(
            False, f"methods disagree: answer {a!r} vs check {c!r}", disagree=True
        )
    return Verdict(True)


def flat_numbers(result: dict[str, Any]) -> dict[str, float]:
    """final.numbers is flat {name: number}; the unit goes into the key name."""
    out: dict[str, float] = {}
    named = [("answer", result.get("answer")), ("check", result.get("check"))]
    named += list((result.get("values") or {}).items())
    for name, node in named:
        q = _quantity(node)
        if q is not None:
            out[f"{name} ({q[1]})" if q[1] not in ("-", "") else name] = q[0]
    return out
