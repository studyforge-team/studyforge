"""Unit-conversion factors pass only when the conversion is visible on the same line."""

import pytest

from app.agent.guardrail import check, parse_numbers


def bad(answer: str, pool: list[float], q: list[tuple[float, str]] = ()) -> list[str]:  # type: ignore[assignment]
    return [f.text for f in check(answer, pool, q).unsupported]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (r"50 \times 10^{5}", 5e6),
        (r"50 \times 10^5", 5e6),
        ("5 × 10⁵", 5e5),
        ("5 × 10^{5}", 5e5),
        ("2 × 10⁻³", 2e-3),
    ],
)
def test_sci_notation_parses(text: str, value: float) -> None:
    vals = [f.value for f in parse_numbers(text)]
    assert vals == [pytest.approx(value)]


@pytest.mark.parametrize(
    ("answer", "pool"),
    [
        ("P = 50 × 10⁵ Pa", [50]),
        (r"P = 50 \times 10^{5} Pa", [50]),
        ("t = 2 × 3600 = 7200 s", [2]),
        ("1000 L/m³", []),
        ("V = 12.5 L = 0.0125 m^3", [12.5]),
        ("t = 2.5 h = 9000 s", [2.5]),
        ("t = 7 min = 420 s", [7]),
        ("P = 3.2 bar = 320000 Pa", [3.2]),
        ("m = 4.7 kg = 4700 g", [4.7]),
        ("c = 0.35 mol/L = 350 mol/m³", [0.35]),
        ("flow = 0.03 / 3600", [0.03]),
        ("x = 0.9 * 1000", [0.9]),
    ],
)
def test_visible_conversion_passes(answer: str, pool: list[float]) -> None:
    assert bad(answer, pool) == []


@pytest.mark.parametrize(
    ("answer", "pool"),
    [
        ("Q = 2000 W", [2]),
        ("The value is 4321.", [2]),
        ("t = 7200 s", [2]),
        ("Q = 2000 W\nusing 1000 elsewhere", [2]),  # factor on another line
        ("V = 0.0125 m^3", [12.5]),  # only one unit of the pair
    ],
)
def test_invisible_conversion_flagged(answer: str, pool: list[float]) -> None:
    assert bad(answer, pool) != []


def test_prefix_slip_still_flagged() -> None:
    assert bad("p = 2.5 MPa", [2.5], [(2.5, "kPa")]) == ["2.5"]
    assert bad("p = 2.5 kPa", [2.5], [(2.5, "kPa")]) == []
