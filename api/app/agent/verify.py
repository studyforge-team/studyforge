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


# WP2 sanity limits, by key name (lower-cased) and unit. Unit guards keep a position
# "x (m)" or a stress "yield (Pa)" out of the 0..1 rule.
_FRACTION = re.compile(
    r"conversion|efficien|fraction|mole_frac|yield|selectivity|(?:^|_)(?:eta|x|y)(?:_|\d|$)"
)
_PERCENT = re.compile(r"percent|pct")
_FACTOR = re.compile(r"factor|_per_")  # "conversion_factor" = 1000 is not a fraction
_STAGES = re.compile(r"stage|tray|n_min")
_ASKS_STAGES = re.compile(
    r"(?i)\b(?:number|no\.) of (?:\w+ ){0,2}(?:stages|trays|plates)\b"
    r"|\b(?:stages|trays|plates) (?:are )?(?:required|needed)\b"
)
_FEED_STAGE = re.compile(r"feed_?(?:stage|tray)")
_STAGE_COUNT = re.compile(
    r"^(?:n_?)?(?:total_)?(?:stages|trays)$|^n_(?:theoretical|total)"
)
_DELTA = re.compile(r"gauge|delta|drop|(?:^|_)d[tp](?:_|$)|rise|diff|change")
_FLOW = re.compile(r"flow|volume")
_SIGNED = re.compile(r"heat|work|energy|duty|power|enthalp")  # sign = direction
_DELTA_Q = re.compile(
    r"(?i)\b(?:change|rise|drop|differen|increase|decrease|loss|gauge|Δ|delta)"
)
_PRESSURE = {"pa", "kpa", "bar", "atm"}
_FLOW_UNITS = {
    f"{a}/{t}" for a in ("mol", "kmol", "kg", "g", "m^3", "m3", "l") for t in ("s", "min", "h", "hr")
}


def _sanity_one(name: str, value: float, unit: str, delta_ok: bool) -> str | None:
    key, u = name.lower(), unit.lower()
    delta_ok = delta_ok or _DELTA.search(key) is not None
    if _PERCENT.search(key):
        if not 0 <= value <= 100:
            return f"{name} = {value:g} is outside 0-100 %"
    elif unit == "-" and _FRACTION.search(key) and not _FACTOR.search(key):
        if not 0 <= value <= 1:
            return f"{name} = {value:g} is a fraction and must be between 0 and 1"
    elif (
        (unit == "-" or u in ("stage", "stages", "tray", "trays"))
        and _STAGES.search(key)
        and not 1 <= value <= 150  # Gilliland/Kremser give fractional stages
    ):
        return f"{name} = {value:g} must be a whole number of stages from 1 to 150"
    if not delta_ok and ((u == "k" and value <= 0) or (u in _PRESSURE and value <= 0)):
        return f"{name} = {value:g} {unit} must be above zero"
    flow_unit = u.replace(" ", "") in _FLOW_UNITS  # L, V, L_bar ... named by symbol only
    if (_FLOW.search(key) or flow_unit) and not _DELTA.search(key) and not _SIGNED.search(key) and value < 0:
        return f"{name} = {value:g} is a flow or volume and cannot be negative"
    return None


def sanity(result: Any, question: str = "") -> str | None:
    """A rule the result breaks (physically impossible numbers), else None."""
    if not isinstance(result, dict):
        return None
    named = [("answer", result.get("answer")), ("check", result.get("check"))]
    named += [(str(k), v) for k, v in (result.get("values") or {}).items()]
    delta_q = _DELTA_Q.search(question) is not None
    # one-quantity question asking for stages: the answer itself is the stage count
    asks_stages = _ASKS_STAGES.search(question) is not None and asked_parts(question) < 2
    stage_n: float | None = None
    feed: float | None = None
    for name, node in named:
        if not isinstance(node, dict):
            continue
        raw = node.get("value")
        if isinstance(raw, float) and not math.isfinite(raw):
            return f"{name} is not a finite number"
        q = _quantity(node)
        if q is None:
            continue
        if why := _sanity_one(
            name, q[0], q[1], delta_q and name in ("answer", "check")
        ):
            return why
        if asks_stages and name in ("answer", "check") and not 1 <= q[0] <= 150:
            return f"{name} = {q[0]:g} cannot be a number of stages (must be 1 to 150)"
        key = name.lower()
        if _FEED_STAGE.search(key):
            feed = q[0]
        elif _STAGE_COUNT.search(key):
            stage_n = q[0]
    if feed is not None and stage_n is not None and feed > stage_n:
        return f"feed stage {feed:g} is beyond the {stage_n:g} stages"
    if feed is not None and feed < 1:
        return f"feed stage {feed:g} must be at least 1"
    return None


_MARKS = re.compile(r"\(([a-d])\)")
_CLAUSE = re.compile(
    r"(?i)\band\s+(?:find|report|give|state|compute|determine|say|also)\b"
)
_ALSO = re.compile(r"(?:^|[.!?]\s+)Also\b")


def asked_parts(question: str) -> int:
    """How many quantities the question asks for (at least 1)."""
    if marks := {m.lower() for m in _MARKS.findall(question)}:
        return len(marks)
    return 1 + len(_CLAUSE.findall(question)) + (_ALSO.search(question) is not None)


def missing_parts(result: Any, question: str) -> str | None:
    """A repair message when result["parts"] lists fewer quantities than asked."""
    asked = asked_parts(question)
    if asked < 2 or not isinstance(result, dict):
        return None
    raw = result.get("parts")
    values = result.get("values")
    known = set(values) if isinstance(values, dict) else set()
    given = [p for p in raw if p == "answer" or p in known] if isinstance(raw, list) else []
    if isinstance(raw, list) and len(given) >= asked and len(given) == len(raw):
        return None
    return (
        f"The question asks for {asked} quantities; your result has {len(given)}. "
        "Keep your method and numbers; add each missing quantity to values and list "
        "all of them in parts."
    )


def verify(result: Any, question: str = "") -> Verdict:
    """Canonical result: {"answer": {value, unit}, "check": {value, unit, method},
    "values": {name: {value, unit}}}. Both methods must agree and be physically possible."""
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
    if (why := sanity(result, question)) is not None:
        return Verdict(False, f"impossible value: {why}")
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
