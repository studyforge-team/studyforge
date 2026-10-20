import json
from pathlib import Path
from typing import Any

import pytest

from app.agent import loop
from app.agent.guardrail import allowed_numbers, check, parse_unit
from app.agent.verify import verify

ROWS = json.loads((Path(__file__).parent / "sv4b_rows.json").read_text("utf-8"))


def result_of(numbers: dict[str, float]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, v in numbers.items():
        name, _, unit = key.partition(" (")
        out[name] = {"value": v, "unit": unit.rstrip(")")}
    return out


def flags(answer: str, result: dict[str, Any], question: str = "") -> list[str]:
    return loop.b8_guard(answer, {"values": result}, question)


@pytest.mark.parametrize(
    ("unit", "parsed"),
    [
        ("kJ", ("J", 3, 1)), ("m", ("m", 0, 1)), ("mm", ("m", -3, 1)),
        ("mol", ("mol", 0, 1)), ("ms", ("s", -3, 1)), ("Pa", ("Pa", 0, 1)),
        ("kPa", ("Pa", 3, 1)), ("mm^2", ("m", -3, 2)), ("m2", ("m", 0, 2)),
        ("m³", ("m", 0, 3)), ("cm^{3}", ("m", -2, 3)), ("µm", ("m", -6, 1)),
        ("mmHg", None), ("min", None), ("K", None), ("bar", None), ("%", None),
        ("mol/h", None),
    ],
)  # fmt: skip
def test_parse_unit(unit: str, parsed: object) -> None:
    assert parse_unit(unit) == parsed


def test_real_rows_conversions_not_flagged() -> None:
    r = ROWS["border_current_density"]
    bad = flags(r["answer_md"], result_of(r["numbers"]))
    assert not any(t.startswith("3.14159") for t in bad)
    assert not any("10^{-6}" in t for t in bad)
    r = ROWS["h_tiny_photon"]
    assert not any(
        "10^{-9}" in t for t in flags(r["answer_md"], result_of(r["numbers"]))
    )
    # 209200 appears as "J/K" in the live row (no conversion); with a kJ result the
    # "209200 J" form is a plain conversion
    r = ROWS["prop_water_heating"]
    text = r["answer_md"].replace("209200 J/K", "209200 J")
    assert "209200" in flags(r["answer_md"], result_of(r["numbers"]))
    assert "209200" not in flags(text, {"Q": {"value": 209.2, "unit": "kJ"}})


def test_unsafe_shift_regressions() -> None:
    res = {"Q": {"value": 4514, "unit": "kJ"}}
    for ok in ("4514 kJ", "4.514 MJ", "4514000 J"):
        assert flags(ok, res) == []
    assert flags("4.514e+06 kJ", res) == ["4.514e+06"]
    assert flags("4514000 kJ", res) == ["4514000"]
    res = {"n": {"value": 300, "unit": "mol/h"}}
    assert flags("3000 mol/h", res) == ["3000"]
    assert flags("0.3 mol/h", res) == ["0.3"]


def test_area_power() -> None:
    res = {"A": {"value": 3.14159, "unit": "mm^2"}}
    assert flags("3.14159e-6 m^2", res) == []
    assert flags("3.14159e-3 m^2", res) == ["3.14159e-3"]
    assert flags(r"3.14159 \times 10^{-6}\ \text{m}^2", res) == []


def test_percent() -> None:
    res = {"X": {"value": 0.667, "unit": "-"}}
    assert flags("66.7%", res) == []
    assert flags("6.67", res) == ["6.67"]
    assert flags("66.7", res) == ["66.7"]
    assert flags("90%", {}, "90% conversion") == []
    assert flags("0.9", {}, "90% conversion") == []
    assert flags("0.9", {}, "ninety conversion") == ["0.9"]


def test_bare_power_of_ten_and_pi() -> None:
    assert flags("10^{-9} and 10⁵ and 10^{12}", {}) == []
    assert flags("10^{13}", {}) == ["10^{13}"]
    assert flags("3.1416", {}) == []


def test_invented_unchanged() -> None:
    res = {"assumptions": ["rho = 998 kg/m3"]}
    assert loop._invented(res, "water in a pipe") is True
    assert loop._invented(res, "rho = 998 kg/m3") is False


def test_tiny_numbers_not_equal() -> None:
    res = {"E": {"value": 3.97e-19, "unit": "J"}}
    assert flags("1.0e-19", res) == ["1.0e-19"]
    assert check("1.0e-19", allowed_numbers(res, "")).ok is False
    assert verify({"answer": {"value": 1.0e-19, "unit": "J"},
                   "check": {"value": 3.97e-19, "unit": "J"}}).disagree  # fmt: skip
    assert verify({"answer": {"value": 0, "unit": "J"},
                   "check": {"value": 0, "unit": "J"}}).ok  # fmt: skip
