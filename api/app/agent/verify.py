"""Server-side caps on posted sandbox results, and the deterministic verify step.

Caps follow what the browser worker really sends: up to 4 figures as bare base64
PNG (<= 500 KB decoded each), stdout up to 64 KB plus a truncation note, and a
result capped at 16 KB in solve mode (a little slack for re-serialisation).
"""

import base64
import binascii
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.agent.steps import ResultBody

MAX_FIGURES = 4
MAX_FIGURE_BYTES = 500 * 1024
MAX_STDOUT = 64 * 1024
MAX_RESULT_JSON = 16 * 1024 + 1024
MAX_ERROR = 2000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
AGREE_REL = 5e-3  # the two methods must agree to 0.5 % (= guardrail REL_TOL)


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
    if value is None or not (unit is None or isinstance(unit, str)):
        return None
    unit = (unit or "").strip()
    return value, "-" if unit.lower() in ("", "dimensionless", "1") else unit


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
    a, c = answer[0], check[0]
    if abs(a - c) > AGREE_REL * max(abs(a), abs(c)):
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


# SV8: an adiabatic exothermic reactor never leaves colder than its feed. Narrow on
# purpose: any doubt about the question (cooling, a temperature-change ask, no feed
# label) means no check rather than a false alarm.
_ADIABATIC = re.compile(r"(?i)\badiabatic")
_EXO = re.compile(
    r"(?i)exotherm|(?:heat|enthalpy) of reaction\D{0,15}[-−]\d"
    r"|(?:ΔH|delta ?H)\w*\s*[=:]?\s*[-−]\s*\d"
)
_SKIP = re.compile(
    r"(?i)cool(?:ant|ing|ed|er)|jacket|heat exchang|quench|steam|heating (?:medium|fluid)"
    r"|temperature (?:rise|change|increase|difference|drop|jump)"
    r"|(?:rise|increase|change) in temperature|Δ ?T\b|delta[ _]?T\b|\bdT\b"
)
# first temperature within 30 chars of a feed label; no sentence break, decimals ok
_FEED = re.compile(
    r"(?i)\b(?:T_?0|T_in|feed|inlet|enter|initial|starting)(?:[^.]|(?<=\d)\.(?=\d)){0,30}?"
    r"(\d+(?:\.\d+)?)(?:\s*(K)\b|\s*°\s*C|\s*deg\s*C\b|C\b)"
)
_TEMP_KEY = re.compile(r"^(.*) \((K|°C|degC|C)\)$")
_OUTLET = re.compile(r"(?i)exit|outlet|out\b|final|product|end\b")
_NOT_OUTLET = re.compile(
    r"(?i)ref|std|standard|feed|inlet|initial|T_?0|rise|delta|change|diff|\bdT|increase|drop|ad\b"
)


def energy_sign_problem(
    numbers: dict[str, float], question: str
) -> tuple[float, float] | None:
    """(outlet T, feed T) in K when a named outlet temperature of an adiabatic
    exothermic reactor is below its feed temperature, else None."""
    if not (_ADIABATIC.search(question) and _EXO.search(question)):
        return None
    if _SKIP.search(question):
        return None
    m = _FEED.search(re.sub(r"(?<=\d),(?=\d{3}\b)", "", question))
    if not m:
        return None
    t0 = float(m.group(1)) + (0 if m.group(2) else 273.15)
    for key, value in numbers.items():
        k = _TEMP_KEY.match(key)
        if k and _OUTLET.search(k.group(1)) and not _NOT_OUTLET.search(k.group(1)):
            t = value + (0 if k.group(2) == "K" else 273.15)
            if t < t0 - 0.5:
                return t, t0
    return None
