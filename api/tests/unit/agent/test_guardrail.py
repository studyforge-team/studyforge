import pytest

from app.agent.guardrail import allowed_numbers, check, parse_numbers


def flagged(
    answer: str, result: object = None, question: str = "", unit: bool = False
) -> list[str]:
    q = [(v["value"], v["unit"]) for v in (result or {}).values() if unit]  # type: ignore[attr-defined]
    report = check(answer, allowed_numbers(result or {}, question), q)
    assert report.ok == (not report.unsupported)
    return [f.text for f in report.unsupported]


# ---- planted errors -------------------------------------------------------
def test_planted_wrong_number_caught() -> None:
    assert flagged("X is 0.7123", {"X": 0.6667}) == ["0.7123"]


def test_decimal_slip_caught() -> None:
    assert flagged("X is 6.67", {"X": 0.667}) == ["6.67"]


def test_kpa_pa_slip_caught() -> None:
    result = {"P": {"value": 101325.0, "unit": "Pa"}}
    assert flagged("P = 101.3 kPa", result, unit=True) == []  # real conversion now ok
    assert flagged("P = 101.3 Pa", result, unit=True) == ["101.3"]
    assert flagged("P = 101325 Pa", result, unit=True) == []
    assert flagged("P = 98000 Pa", {"P": {"value": 98000.0}}) == []


def test_percent_of_fraction_allowed() -> None:
    assert flagged("X = 66.7%", {"X": 0.667}) == []
    assert flagged(r"X = 66.7\%", {"X": 0.667}) == []


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
    "answer", ["1,234.5", "1.2e-3", r"1.2 \times 10^{-3}", "−0.42"]
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


def test_latex_command_glued_to_a_number_is_not_part_of_it() -> None:
    b = chr(92)
    s = f"T {b}approx79.8957 K"
    found = parse_numbers(s)
    assert [f.value for f in found] == [79.8957]
    assert s[found[0].start :].startswith("79.8957")
    assert [f.value for f in parse_numbers(f"{b}tfrac12")] == []
    assert [f.value for f in parse_numbers(f"3{b}times4.2")] == [3, 4.2]
    assert [f.value for f in parse_numbers(f"2.5{b}times10^{{5}}")] == [250000]
    assert [f.value for f in parse_numbers(f"3{b}cdot10^{{-4}}")] == [3e-4]
    assert [f.value for f in parse_numbers(f"{b}approx123")] == [123]


def test_divisor_100_and_1000_not_flagged() -> None:
    assert flagged("ln(1 - 90/100) and (200 / 1000) / 1.2", {"X": 90.0}, "200 1.2") == []
    assert flagged("so 100 is the answer", {"X": 5.0}) == ["100"]
    assert flagged("X is 5/37", {"X": 5.0}) == ["37"]


def test_correlation_constants_pass_only_exactly() -> None:
    assert flagged("Colebrook: 1/sqrt(f) = -2 log(e/(3.7 D) + 2.51/(Re sqrt(f)))") == []
    assert flagged("Stokes: u = g d^2 (rho_p - rho) / (18 mu)") == []
    assert flagged("u = 2.52") == ["2.52"]  # near a constant is not the constant


def test_one_difference_of_given_numbers_is_allowed() -> None:
    from app.agent.guardrail import allowed_numbers, check

    q = "A sphere at 300 C is cooled in air at 20 C. Particle 2650 kg/m3 in water 998 kg/m3; X = 0.85."
    allowed = allowed_numbers({}, q)
    assert check("dT = 280 K, drho = 1652 kg/m3, 1 - X = 0.15", allowed).ok
    assert not check("dT = 290 K", allowed).ok


def test_formula_constants_pass_only_inside_a_formula() -> None:
    pool = [0.5]
    assert check("Nu = 0.023 Re^0.8 Pr^0.4", pool).ok
    assert check(r"v_t = \frac{g d^2 \Delta\rho}{18 \mu}", pool).ok
    assert check(r"$\frac{1}{\sqrt f} = -2\log(\frac{e/D}{3.7} + \frac{2.51}{Re\sqrt f})$", pool).ok
    assert not check("The reactor volume is 24 m^3.", pool).ok
    assert not check("V = 150 L", pool).ok


def test_every_number_of_a_data_table_in_the_question_counts_as_given() -> None:
    table = "\n".join(f"{p:.2f} " + " ".join(f"0.{9000 + p * 37:.0f}" for _ in range(5)) for p in range(1, 15))
    q = "Use the Z table below.\n" + table + "\nThe last entry is 0.71727 at 15.41 bar."
    allowed = allowed_numbers({}, q)
    assert 0.71727 in allowed and 15.41 in allowed  # beyond the first 40 numbers


def test_latex_thin_space_thousands_is_one_number() -> None:
    assert [f.value for f in parse_numbers(r"H = 18\,115.0 J and 1\,000\,000 then 7")] == [18115.0, 1000000.0, 7.0]
    assert [f.value for f in parse_numbers(r"0.5\,3 and 12\,34")] == [0.5, 3.0, 12.0, 34.0]
