"""Unit-prefix rescales: only the exact rescale the two units imply may pass."""

from typing import Any

import pytest

from app.agent.guardrail import allowed_numbers, check, parse_unit


def real(answer: str, value: float, unit: str) -> list[str]:
    """Through the real pipeline: allowed pool holds the raw sandbox value."""
    res: dict[str, Any] = {"values": {"X": {"value": value, "unit": unit}}}
    rep = check(answer, allowed_numbers(res, ""), [(value, unit)])
    return [f.text for f in rep.unsupported]


def direct(answer: str, value: float, unit: str) -> list[str]:
    """Direct check with the quantity only (no raw value in the pool)."""
    return [f.text for f in check(answer, [], [(value, unit)]).unsupported]


GOOD = [
    (2.5, "kPa", "2500 Pa"),
    (2.5, "kPa", "0.0025 MPa"),
    (2.5, "kPa", "2.5 kPa"),
    (1200, "W", "1.2 kW"),
    (0.0042, "m^3", "4200000 mm^3"),
]
SLIPS = [
    (2.5, "kPa", "2.5 MPa"),
    (2.5, "kPa", "2500 MPa"),
    (2.5, "kPa", "2.5 Pa"),
    (1200, "W", "1200 kW"),
    (0.0042, "m^3", "4.2 mm^3"),
    (0.0042, "m^3", "0.0042 mm^3"),
]


@pytest.mark.parametrize(("v", "u", "ans"), GOOD)
def test_correct_rescale_passes(v: float, u: str, ans: str) -> None:
    assert direct(ans, v, u) == []


@pytest.mark.parametrize(("v", "u", "ans"), SLIPS)
def test_slip_flagged_direct(v: float, u: str, ans: str) -> None:
    assert direct(ans, v, u) != []


@pytest.mark.parametrize(("v", "u", "ans"), SLIPS)
def test_slip_flagged_real_pipeline(v: float, u: str, ans: str) -> None:
    assert real(ans, v, u) != []


def test_litre_has_no_relation_to_cubic_metres() -> None:
    # parse_unit knows L but not L == 1e-3 m^3, so "4.2 L" for 0.0042 m^3 is not accepted
    # (stays flagged; a correct-conversion case is skipped on purpose)
    assert parse_unit("L") == ("L", 0, 1)
    assert direct("4.2 L", 0.0042, "m^3") != []
