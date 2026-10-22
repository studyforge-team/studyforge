import base64
import json
from pathlib import Path
from typing import Any

import pytest

from app.agent.steps import ResultBody
from app.agent.tools import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    ToolRefused,
    check_mermaid,
    parse_args,
)
from app.agent.verify import (
    MAX_STDOUT,
    clean,
    energy_sign_problem,
    flat_numbers,
    verify,
)

OK = {
    "answer": {"value": 2.0, "unit": "m"},
    "check": {"value": 2.0005, "unit": "m", "method": "numeric"},
}
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 10


def test_exactly_six_tools() -> None:
    assert TOOL_NAMES == (
        "run_python",
        "search_my_notes",
        "web_search",
        "make_quiz",
        "schedule_reminder",
        "draw_diagram",
    )
    assert len(TOOL_SCHEMAS) == 6


@pytest.mark.parametrize(
    ("name", "args", "msg"),
    [
        ("exec_shell", "{}", "unknown tool"),
        ("run_python", "not json", "not valid JSON"),
        ("run_python", "[1]", "JSON object"),
        ("web_search", "{}", "missing query"),
    ],
)
def test_bad_tool_calls_are_refused(name: str, args: str, msg: str) -> None:
    with pytest.raises(ToolRefused, match=msg):
        parse_args(name, args)


def test_mermaid_checks() -> None:
    assert check_mermaid("  graph TD; A-->B ") == "graph TD; A-->B"
    for bad in ("", "x" * 5000, "<script>alert(1)</script>"):
        with pytest.raises(ToolRefused):
            check_mermaid(bad)


def test_verify_accepts_two_agreeing_methods() -> None:
    assert verify(OK).ok


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        ([1, 2], "must be a dict"),
        ({"check": OK["check"]}, "answer"),
        ({"answer": {"value": "2.0", "unit": "m"}, "check": OK["check"]}, "answer"),
        ({"answer": {"value": True, "unit": "m"}, "check": OK["check"]}, "answer"),
        (
            {"answer": {"value": float("nan"), "unit": "m"}, "check": OK["check"]},
            "answer",
        ),
        ({"answer": OK["answer"]}, "check"),
        ({**OK, "check": {"value": 2.0, "unit": "cm"}}, "unit"),
    ],
)
def test_verify_rejects_bad_shapes(result: Any, reason: str) -> None:
    v = verify(result)
    assert not v.ok and reason in (v.reason or "") and not v.disagree


def test_verify_flags_disagreement() -> None:
    v = verify({**OK, "check": {"value": 2.1, "unit": "m"}})
    assert (v.ok, v.disagree) == (False, True)


FIXTURES = json.loads(Path(__file__).with_name("sv4a_fixtures.json").read_text())


@pytest.mark.parametrize(
    "name", ["batch_time", "biot", "integral", "ode_numeric_tolerance", "prandtl"]
)
def test_sv4a_correct_results_pass(name: str) -> None:
    assert verify(FIXTURES[name]).ok


def test_sv4a_dimensionless_vs_unit_still_fails() -> None:
    v = verify(FIXTURES["mach_bad_check_MUST_STILL_FAIL"])
    assert not v.ok and "unit" in (v.reason or "")


def test_helper_values_need_not_be_quantities() -> None:
    assert verify({**OK, "values": {"s": "text", "flag": True}}).ok


def test_agreement_is_half_a_percent() -> None:
    assert verify({**OK, "check": {"value": 2.006, "unit": "m"}}).ok
    v = verify({**OK, "check": {"value": 2.02, "unit": "m"}})
    assert (v.ok, v.disagree) == (False, True)


def test_flat_numbers_dimensionless_answer_key() -> None:
    assert flat_numbers(FIXTURES["integral"])["answer"] == pytest.approx(
        0.71828, abs=1e-5
    )


def test_flat_numbers_put_units_in_keys() -> None:
    result = {**OK, "values": {"X": {"value": 0.5, "unit": "-"}, "bad": {"value": "x"}}}
    assert flat_numbers(result) == {"answer (m)": 2.0, "check (m)": 2.0005, "X": 0.5}


def test_clean_caps_what_the_worker_sends() -> None:
    good = base64.b64encode(PNG).decode()
    big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * 600_000).decode()
    jpeg = base64.b64encode(b"\xff\xd8\xff" + b"x" * 10).decode()
    body = ResultBody(
        stdout="a" * (MAX_STDOUT + 10),
        result=OK,
        figures=[good, big, jpeg, "!!notbase64", good],
        error=None,
    )
    out = clean(body)
    assert len(out.stdout) == MAX_STDOUT
    assert out.figures == ["data:image/png;base64," + good]  # only first 4 considered
    assert out.result == OK


def test_clean_rejects_oversized_or_non_json_result() -> None:
    assert (
        clean(ResultBody(result={"x": "y" * 20000})).error
        == "result too large or not JSON"
    )
    assert clean(ResultBody(result=float("nan"))).result is None
    assert clean(ResultBody(error="e" * 5000)).error == "e" * 2000


REAL_Q = (
    "Liquid A -> B (first order, k = 3.0e11 exp(-75000/(R T)) s^-1, R = 8.314 J/(mol K)) "
    "flows through an adiabatic PFR of volume 400 L. Feed: v0 = 20 L/s, CA0 = 2.0 mol/L, "
    "T0 = 300 K; heat of reaction -60 kJ/mol, volumetric heat capacity rho*Cp = 4000 J/(L K), "
    "constant. Integrate the PFR numerically, plot T and X versus volume, and report the "
    "exit conversion (main answer) and exit temperature in K (second value)."
)
EXIT = "exit_temperature_K (K)"
SIGN_CASES = [  # (question, numbers, trips)
    (REAL_Q, {"answer": 0.277, "check": 0.2775, EXIT: 291.68}, True),  # live 22 Oct
    (
        "Adiabatic CSTR, ΔH_rxn = −60 kJ/mol, feed T0 = 350 K.",
        {"exit_T (K)": 330.0},
        True,
    ),
    ("Adiabatic exothermic reactor, feed 300 K.", {"T_out (°C)": 20.0}, True),
    (REAL_Q, {"answer": 0.87, EXIT: 326.247, "T_ref (K)": 298.15}, False),
    (REAL_Q, {EXIT: 326.247, "T_ad (K)": 60.0}, False),
    (REAL_Q, {EXIT: 326.247, "outlet_temperature_rise (K)": 26.2}, False),
    (
        "Adiabatic exothermic reactor, feed at 300 K. How much does it heat up?",
        {"answer (K)": 60.0},
        False,
    ),
    ("Adiabatic exothermic A -> 2 C, feed 400 K.", {"T_exit (K)": 450.0}, False),
    (
        "Adiabatic reactor, ΔH = -80 kJ/mol at 298 K, feed 400 K.",
        {"T_exit (K)": 450.0},
        False,
    ),
    ("Adiabatic exothermic reactor, feed 1,200 K.", {"T_exit (K)": 1250.0}, False),
    (
        "Adiabatic exothermic beds with an intercooler, feed 400 K.",
        {"T_exit (K)": 380.0},
        False,
    ),
    (
        "Adiabatic exothermic beds with a cold-shot quench, feed 400 K.",
        {"T_exit (K)": 380.0},
        False,
    ),
    (
        REAL_Q.replace("adiabatic PFR", "PFR with a coolant jacket"),
        {EXIT: 291.68},
        False,
    ),
    (
        REAL_Q.replace("reaction -60", "reaction +50"),
        {EXIT: 291.68},
        False,
    ),  # endothermic
    (
        "Adiabatic exothermic reactor, feed 400 K. Find the temperature rise.",
        {"T_exit (K)": 380.0},
        False,
    ),
    (
        "Adiabatic exothermic reactor at 400 K.",
        {"T_exit (K)": 380.0},
        False,
    ),  # no feed label
    ("Adiabatic exothermic reactor, feed 300 K.", {"T_out (°C)": 40.0}, False),
]


@pytest.mark.parametrize(("question", "numbers", "trips"), SIGN_CASES)
def test_energy_sign_problem(
    question: str, numbers: dict[str, float], trips: bool
) -> None:
    assert (energy_sign_problem(numbers, question) is not None) is trips
