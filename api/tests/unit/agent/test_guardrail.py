import pytest

from app.agent.guardrail import allowed_numbers, check, parse_numbers


def flagged(answer: str, result: object = None, question: str = "") -> list[str]:
    report = check(answer, allowed_numbers(result or {}, question))
    assert report.ok == (not report.unsupported)
    return [f.text for f in report.unsupported]


# ---- planted errors -------------------------------------------------------
def test_planted_wrong_number_caught() -> None:
    assert flagged("X is 0.7123", {"X": 0.6667}) == ["0.7123"]


def test_decimal_slip_caught() -> None:
    assert flagged("X is 6.67", {"X": 0.667}) == ["6.67"]


def test_kpa_pa_slip_caught() -> None:
    result = {"P": {"value": 101325.0}}
    assert flagged("P = 101.3 kPa", result) == ["101.3"]
    assert flagged("P = 101325 Pa", result) == []
    assert flagged("P = 98000 Pa", {"P": {"value": 98000.0}}) == []


def test_percent_needs_percent_value() -> None:
    assert flagged("X = 66.7%", {"X": 0.667}) == ["66.7"]
    assert flagged(r"X = 66.7\%", {"X": 0.667, "X_percent": 66.7}) == []


@pytest.mark.parametrize(
    ("answer", "value"),
    [
        ("0.6667", 0.666667),
        (r"1.235 \times 10^{6}", 1234567.0),
        ("1.235×10^6", 1234567.0),
        ("3.2", -3.2),
    ],
)
def test_rounding_and_sign_pass(answer: str, value: float) -> None:
    assert flagged(answer, {"v": value}) == []


def test_tolerance_edges() -> None:
    assert flagged("100.4", {"v": 100.0}) == []
    assert flagged("100.6", {"v": 100.0}) == ["100.6"]
    assert flagged("99.4", {"v": 100.0}) == ["99.4"]


# ---- allowed set ----------------------------------------------------------
def test_question_numbers_pass() -> None:
    assert flagged("At 350 K and 2.5 mol/L", {}, "T = 350 K, C = 2.5 mol/L") == []


def test_small_integers_pass() -> None:
    assert flagged("-10 and 7 and 0 and 10") == []
    assert flagged("11") == ["11"]
    assert flagged("2.5") == ["2.5"]


@pytest.mark.parametrize(
    "c", ["8.314", "9.81", "6.022e23", "273.15", "101325", "0.08206"]
)
def test_constants_pass(c: str) -> None:
    assert flagged(f"use {c}") == []


def test_strings_lists_series_do_not_count() -> None:
    result = {
        "s": "123.45",
        "arr": [987.6],
        "t": (555.5,),
        "series": {"y": 777.7},
        "b": True,
    }
    assert flagged("123.45 987.6 555.5 777.7", result) == [
        "123.45",
        "987.6",
        "555.5",
        "777.7",
    ]


def test_nested_dict_values_count() -> None:
    assert flagged("42.5", {"a": {"b": {"c": 42.5}}}) == []
    assert allowed_numbers({"a": {"x": 1.5}, "series": 9.9, "ok": True}, "n 3.5") == [
        1.5,
        3.5,
    ]


# ---- skip cases -----------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "C_{A0} and C_{12.5}",
        "T_2 and x_1",
        "H2O and CO2 and k1",
        "unit m^2 and s^{-1} and x^{2} and x^{37}",
        "m³ and m² and kg⁻³",
        "the 2nd, 3rd, 1st, 4th, 22nd",
        "Step 47: Eq. 33 Equation 34 Figure 35 Table 36 Section 37 §38.2",
        "step 47 Figure 2.13",
        "17. first\n23) second\n  45. third",
        "`x = 3333`",
        "```python\nx = 4444.5\nprint(x)\n```",
    ],
)
def test_skips(text: str) -> None:
    assert flagged(text) == []


def test_list_marker_only_at_line_start() -> None:
    assert flagged("value 47. next") == ["47"]


def test_code_masking_keeps_offsets() -> None:
    answer = "`a` then 55.5"
    [f] = check(answer, []).unsupported
    assert answer[f.start : f.start + len(f.text)] == "55.5"


# ---- formats --------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "values"),
    [
        ("42", [42]),
        ("3.14", [3.14]),
        (".5", [0.5]),
        ("1,234.5", [1234.5]),
        ("1,234,567", [1234567]),
        ("1,2345", [1, 2345]),
        ("1.2e-3", [1.2e-3]),
        ("1.2E+3", [1200]),
        ("1.2×10^-3", [1.2e-3]),
        (r"1.2 \times 10^{-3}", [1.2e-3]),
        (r"1.2 \cdot 10^{3}", [1200]),
        ("1.2 × 10^{−3}", [1.2e-3]),
        ("10^{-3}", [1e-3]),
        ("10^5", [1e5]),
        ("3.2 × 10⁵", [3.2e5]),
        ("1.2×10⁻³", [1.2e-3]),
        ("10⁻¹²", [1e-12]),
        ("k = 4.1 s⁻¹", [4.1]),
        ("−3.2", [3.2]),
        ("-3.2", [3.2]),
        (r"\frac{1}{3}", [1, 3]),
        (r"\frac{22}{7}", [22, 7]),
        ("66.7%", [66.7]),
        (r"66.7\%", [66.7]),
        ("x^2 is 9.5", [9.5]),
    ],
)
def test_parse_formats(text: str, values: list[float]) -> None:
    assert [f.value for f in parse_numbers(text)] == pytest.approx(values)


@pytest.mark.parametrize(
    "answer", ["1,234.5", "1.2e-3", r"1.2 \times 10^{-3}", "10^{-3}", "−0.42"]
)
def test_formats_checked_against_allowed(answer: str) -> None:
    nums = [parse_numbers(answer)[0].value]
    assert check(answer, []).ok is False
    assert check(answer, nums).ok is True


def test_sci_scale_shift_caught() -> None:
    # a Unicode superscript exponent must not hide a scale shift
    assert flagged("k = 3.2 × 10⁵ s⁻¹", {"k": 3.2}) == ["3.2 × 10⁵"]
    assert flagged("k = 3.2 × 10⁵ s⁻¹", {"k": 3.2e5}) == []
    assert flagged(r"1.2 \times 10^{3}", {"v": 1.2e-3}) != []
    assert flagged("1200", {"v": 1.2}) == ["1200"]


# ---- sign and zero --------------------------------------------------------
def test_sign_ignored_both_ways() -> None:
    assert flagged("releases 3.2 kJ", {"dH": -3.2}) == []
    assert flagged("ΔH = −3.2", {"dH": 3.2}) == []


def test_zero_handling() -> None:
    assert flagged("0.0") == []
    assert flagged("0.001", {"v": 0.0}) == ["0.001"]
    assert flagged("1e-15", {"v": 0.0}) == []
    assert flagged("0.5", {"v": 0.0}) == ["0.5"]


# ---- positions ------------------------------------------------------------
def test_positions_point_at_token() -> None:
    answer = "Rate is 77.7 and, in sci form, 8.8 \\times 10^{4}; also 12,345.6."
    report = check(answer, [])
    assert [f.text for f in report.unsupported] == [
        "77.7",
        "8.8 \\times 10^{4}",
        "12,345.6",
    ]
    for f in report.unsupported:
        assert answer[f.start : f.start + len(f.text)] == f.text
    assert report.unsupported[0].value == 77.7
