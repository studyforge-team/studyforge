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
    101325, 1.01325, 0.08206, math.pi,
)  # fmt: skip
# exact conversion factors; one counts only when visible on the same line (see _conv_fits)
CONVERSIONS: tuple[float, ...] = (1000.0, 3600.0, 60.0, 1e5)


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
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_EXP = (
    rf"\^\s*(?:\{{\s*[{_MINUS}+]?[0-9]+\s*\}}|[{_MINUS}+]?[0-9]+)"
    rf"|[⁻⁺]?[{_SUP}]+"  # Unicode superscript: 10⁵, 10⁻³
)
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
# a LaTeX command glued to a number ("\approx79.8957") must not leak its letters/number into the tokens;
# \times and \cdot before "10" stay (scientific notation)
_GLUED = re.compile(
    r"\\(?:approx|simeq|sim|leq?|geq?|neq?|pm|mp|equiv|quad|qquad|(?:times|cdot)(?!\s*10))(?![A-Za-z])(?=[0-9.])"
)


_DIVISOR = re.compile(r"/\s*$")  # a bare 100 or 1000 right after "/" is a divisor, not a result


def _blank(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", m.group())


def _to_float(s: str) -> float:
    return float(s.replace(",", "").replace("−", "-"))


_FROM_SUP = str.maketrans(_SUP + "⁻⁺", "0123456789-+")


def _exp(s: str) -> str:
    return re.sub(r"[\s{}^]", "", s).translate(_FROM_SUP).replace("−", "-")


def parse_numbers(text: str) -> list[Flagged]:
    """Numbers written in ``text`` (code and identifiers excluded), in order."""
    text = _INLINE.sub(_blank, _FENCE.sub(_blank, text))
    text = _GLUED.sub(_blank, text)
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
    if a == 0 or b == 0:
        return abs(a - b) < ABS_TOL
    return abs(a - b) <= REL_TOL * b


_PREFIX = {"n": -9, "μ": -6, "µ": -6, "u": -6, "m": -3, "c": -2, "k": 3, "M": 6, "G": 9}
_UNIT_RE = re.compile(
    r"([nμµucmkMG]?)(mol|Pa|Hz|[mgsLJWNAV])(?:\^\s*\{?([23])\}?|([23])|([²³]))?"
)


def parse_unit(u: str) -> tuple[str, int, int] | None:
    """'kJ' -> ('J', 3, 1); 'mm^2' -> ('m', -3, 2); None if not a single SI unit."""
    m = _UNIT_RE.fullmatch(u.strip())
    if not m:
        return None
    power = int(m[3] or m[4] or ("²³".index(m[5]) + 2 if m[5] else 1))
    return m[2], _PREFIX.get(m[1], 0), power


# unit right after a number: "209200 J", r"3.1 \, \mathrm{m^2}", "5 mm^2"
_AFTER_UNIT = re.compile(
    r"\s*(?:\\[,; ]\s*)?(?:\\(?:text|mathrm)\{\s*)?"
    r"([A-Za-zμµ]+)\}?((?:\^\s*\{?[23]\}?|[23²³])?)(?![/·\\^A-Za-zμµ0-9²³])"
)
_AFTER_PCT = re.compile(r"\s*\\?%")
_TEN = re.compile(rf"10\s*(?:{_EXP})")


def percents(text: str) -> list[float]:
    """Fractions for numbers written with % in ``text`` (80% -> 0.8)."""
    return [
        f.value / 100
        for f in parse_numbers(text)
        if _AFTER_PCT.match(text, f.start + len(f.text))
    ]


def _prefix_slip(
    f: Flagged,
    answer_md: str,
    end: int,
    hits: Sequence[float],
    quantities: Sequence[tuple[float, str]],
) -> bool:
    """True when the bare-number match is only a sandbox quantity written with a
    different prefix of the same unit (2.5 kPa -> "2.5 MPa"): the value is not rescaled."""
    m = _AFTER_UNIT.match(answer_md, end)
    uw = parse_unit(m[1] + m[2]) if m else None
    if uw is None:
        return False
    same_value = [(v, parse_unit(u)) for v, u in quantities if _close(f.value, v)]
    if not same_value or any(not any(_close(a, v) for v, _ in same_value) for a in hits):
        return False  # also matches a question/assumption number, or no quantity
    return all(
        up is not None and up[0] == uw[0] and up[2] == uw[2] and up[1] != uw[1]
        for _, up in same_value
    )


_W = r"(?<![A-Za-zμµ]){}(?![A-Za-zμµ])"
_M3 = r"(?<![A-Za-z])m\s*(?:\^\s*\{?3\}?|³)"
# a unit pair written on one line makes its factor visible
_UNIT_PAIRS: tuple[tuple[re.Pattern[str], re.Pattern[str], float], ...] = tuple(
    (re.compile(a), re.compile(b), k)
    for a, b, k in (
        (_W.format("L"), _M3, 1000.0),
        (_W.format("g"), _W.format("kg"), 1000.0),
        (_W.format("h"), _W.format("s"), 3600.0),
        (_W.format("min"), _W.format("s"), 60.0),
        (_W.format("bar"), _W.format("Pa"), 1e5),
    )
)
_SCI_PART = re.compile(rf"({_NUM})\s*(?:×|\\times|\\cdot)\s*10")
_OPERATOR = re.compile(r"(?:×|\\times|\\cdot|\*|/)\s*$")
_OPERATOR_AFTER = re.compile(r"\s*(?:×|\\times|\\cdot|\*|/)")


def _conv_fits(f: Flagged, answer_md: str, pool: Sequence[float]) -> bool:
    """f = a x k or a / k (pool number a, factor k) with k visible on f's line."""
    ls = answer_md.rfind("\n", 0, f.start) + 1
    le = answer_md.find("\n", f.start)
    line = answer_md[ls : le if le >= 0 else len(answer_md)]
    off = f.start - ls
    ks = {n.value for n in parse_numbers(line) if n.start != off}
    ks = {k for k in CONVERSIONS if any(_close(k, v) for v in ks)}
    pairs = {k for a, b, k in _UNIT_PAIRS if a.search(line) and b.search(line)}
    ks |= pairs
    end = off + len(f.text)
    if any(_close(f.value, k) for k in pairs):
        return True  # "1000 L/m^3": the factor named by the units
    sci = _SCI_PART.match(f.text)  # "50 x 10^5 Pa": mantissa from the pool, bar -> Pa factor
    if sci:
        man = float(sci[1].replace(",", ""))
        pa = re.compile(r"\s*(?:\\[,; ]\s*)?(?:\\(?:text|mathrm)\{\s*)?Pa\b").match(line, end)
        return any(_close(man, a) for a in pool) and (
            1e5 in pairs or (pa is not None and _close(f.value / man, 1e5))
        )
    if (_OPERATOR.search(line, 0, off) or _OPERATOR_AFTER.match(line, end)) and any(
        _close(f.value, k) for k in CONVERSIONS
    ):
        return True  # a bare factor used as a multiplier / divisor
    return any(_close(f.value, a * k) or _close(f.value, a / k) for a in pool for k in ks)


def _fits(
    f: Flagged, answer_md: str, pool: Sequence[float], quantities: Sequence[tuple[float, str]]
) -> bool:
    end = f.start + len(f.text)
    hits = [a for a in pool if _close(f.value, a)]
    if hits and not _prefix_slip(f, answer_md, end, hits, quantities):
        return True
    if _TEN.fullmatch(f.text) and abs(round(math.log10(f.value))) <= 12:
        return True  # bare power of ten: a conversion factor, not a result
    if _AFTER_PCT.match(answer_md, end) and any(_close(f.value / 100, a) for a in pool):
        return True
    if _conv_fits(f, answer_md, pool):
        return True
    m = _AFTER_UNIT.match(answer_md, end)
    uw = parse_unit(m[1] + m[2]) if m else None
    if uw is None:
        return False
    for v, u in quantities:
        up = parse_unit(u)
        same = up and up[0] == uw[0] and up[2] == uw[2]
        if up and same and _close(f.value, v * 10.0 ** ((up[1] - uw[1]) * up[2])):
            return True
    return False


def check(
    answer_md: str,
    allowed: Sequence[float],
    quantities: Sequence[tuple[float, str]] = (),
) -> GuardrailReport:
    """Flag every number in ``answer_md`` not within 0.5% of an allowed value (or a
    unit conversion of one of ``quantities`` = [(value, unit)])."""
    pool = [*allowed, *CONSTANTS]
    bad = [
        f
        for f in parse_numbers(answer_md)
        if not (f.value.is_integer() and abs(f.value) <= SMALL_INT_MAX)
        and not (f.value in (100, 1000) and _DIVISOR.search(answer_md, 0, f.start))
        and not _fits(f, answer_md, pool, quantities)
    ]
    return GuardrailReport(ok=not bad, unsupported=bad)
