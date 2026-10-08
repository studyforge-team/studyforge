"""Number guardrail: every number in an answer must come from sandbox output.

Pure functions, no I/O. ``allowed_numbers`` collects the numbers an answer may
use; ``check`` flags every other number written in the answer markdown.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

REL_TOL = 0.005
ABS_TOL = 1e-12
SMALL_INT_MAX = 10
CONSTANTS: tuple[float, ...] = (
    8.314, 8.314462618, 9.81, 9.80665, 6.02214076e23, 1.380649e-23,
    96485.33212, 5.670374419e-8, 299792458, 6.62607015e-34, 273.15,
    101325, 1.01325, 0.08206,
)  # fmt: skip


@dataclass(frozen=True)
class Flagged:
    text: str  # the token as written
    value: float
    start: int  # offset in answer_md


@dataclass(frozen=True)
class GuardrailReport:
    ok: bool
    unsupported: list[Flagged] = field(default_factory=list)


_MINUS = "-−"
_EXP = rf"\^\s*(?:\{{\s*[{_MINUS}+]?[0-9]+\s*\}}|[{_MINUS}+]?[0-9]+)"
_NUM = r"(?:[0-9]{1,3}(?:,[0-9]{3})+(?![0-9])|[0-9]+)(?:\.[0-9]+)?|\.[0-9]+"
_TOKEN = re.compile(
    # --- skipped (consumed, never reported) ---
    r"(?<![A-Za-z])(?:Step|step|Eq\.|Equation|Figure|Table|Section)\s*[0-9]+(?:\.[0-9]+)*"
    r"|§\s*[0-9]+(?:\.[0-9]+)*"
    r"|^[ \t]*[0-9]+[.)](?=[ \t])"  # list marker at line start
    r"|_\s*\{[^{}]*\}|_[A-Za-z0-9]"  # subscripts
    r"|\^\s*(?:\{[^{}]*\}|[-−+]?[A-Za-z0-9]+)"  # unit / variable exponents
    # --- numbers ---
    rf"|(?P<sci>(?<![A-Za-z_0-9.])(?P<man>{_NUM})\s*(?:×|\\times|\\cdot)\s*10\s*(?P<e1>{_EXP}))"
    rf"|(?P<ten>(?<![A-Za-z_0-9.])10\s*(?P<e2>{_EXP}))"
    rf"|(?P<num>(?<![A-Za-z_0-9])(?:{_NUM})(?:[eE][-−+]?[0-9]+)?(?![0-9])(?!(?:st|nd|rd|th)\b))",
    re.MULTILINE,
)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]*`")


def _blank(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", m.group())


def _to_float(s: str) -> float:
    return float(s.replace(",", "").replace("−", "-"))


def _exp(s: str) -> str:
    return re.sub(r"[\s{}^]", "", s).replace("−", "-")


def parse_numbers(text: str) -> list[Flagged]:
    """Numbers written in ``text`` (code and identifiers excluded), in order."""
    text = _INLINE.sub(_blank, _FENCE.sub(_blank, text))
    out: list[Flagged] = []
    for m in _TOKEN.finditer(text):
        if m["sci"]:
            value = float(f"{_to_float(m['man'])}e{_exp(m['e1'])}")
        elif m["ten"]:
            value = float(f"1e{_exp(m['e2'])}")
        elif m["num"]:
            value = _to_float(m["num"])
        else:
            continue
        out.append(Flagged(m.group(), value, m.start()))
    return out


def _scalars(node: object) -> list[float]:
    if isinstance(node, bool):
        return []
    if isinstance(node, int | float):
        return [float(node)] if math.isfinite(node) else []
    if isinstance(node, dict):
        return [x for k, v in node.items() if k != "series" for x in _scalars(v)]
    return []  # strings, lists, tuples, anything else


def allowed_numbers(result: object, question: str) -> list[float]:
    """Numbers an answer may cite: sandbox scalars plus numbers in the question."""
    return _scalars(result) + [f.value for f in parse_numbers(question)]


def _close(a: float, b: float) -> bool:
    a, b = abs(a), abs(b)
    if a < ABS_TOL or b < ABS_TOL:
        return abs(a - b) < ABS_TOL
    return abs(a - b) <= REL_TOL * b


def check(answer_md: str, allowed: Sequence[float]) -> GuardrailReport:
    """Flag every number in ``answer_md`` not within 0.5% of an allowed value."""
    pool = [*allowed, *CONSTANTS]
    bad = [
        f
        for f in parse_numbers(answer_md)
        if not (f.value.is_integer() and abs(f.value) <= SMALL_INT_MAX)
        and not any(_close(f.value, a) for a in pool)
    ]
    return GuardrailReport(ok=not bad, unsupported=bad)
