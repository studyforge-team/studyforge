"""Tests for the quiz schema, key checking and solution filling (ticket Q1)."""

import json
import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent.quiz import (
    KeyCheck,
    MCQItem,
    NumericalItem,
    Quiz,
    SubjectiveItem,
    check_key,
    fill_solution,
    parse_quiz,
    quiz_json_schema,
)

FIXTURE = Path(__file__).parents[3] / "app" / "agent" / "fixtures" / "quiz_mock.json"


def mcq(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "mcq",
        "topic": "Thermo",
        "source": None,
        "tags": [],
        "stem": "Which law defines temperature?",
        "options": ["Zeroth", "First", "Second", "Third"],
        "correct_index": 0,
        "misconceptions": {1: "energy", 2: "entropy", 3: "absolute zero"},
        "explanation": "Thermal equilibrium is transitive.",
    }
    base.update(over)
    return base


def num(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "numerical",
        "topic": "Flow",
        "source": "slides-1",
        "tags": ["core"],
        "stem": "Find the flow rate.",
        "key_code": "result = {}",
        "unit": "m3/s",
        "worked_solution": "Q = {answer}, checked as {check}.",
    }
    base.update(over)
    return base


def subj(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "subjective",
        "topic": "Design",
        "source": None,
        "tags": [],
        "stem": "Discuss.",
        "rubric": ["Mentions mixing"],
    }
    base.update(over)
    return base


def quiz(*items: dict[str, Any]) -> dict[str, Any]:
    return {"title": "T", "items": list(items)}


# ---- valid examples -------------------------------------------------------


def test_valid_each_type() -> None:
    q = parse_quiz(quiz(mcq(), num(), subj()))
    assert isinstance(q, Quiz)
    assert [type(i) for i in q.items] == [MCQItem, NumericalItem, SubjectiveItem]


def test_numerical_defaults() -> None:
    item = parse_quiz(quiz(num())).items[0]
    assert isinstance(item, NumericalItem)
    assert item.tolerance_rel == 0.01


def test_json_text_input() -> None:
    q = parse_quiz(json.dumps(quiz(mcq(misconceptions={"1": "a", "2": "b", "3": "c"}))))
    item = q.items[0]
    assert isinstance(item, MCQItem)
    assert item.misconceptions == {1: "a", 2: "b", 3: "c"}


def test_discriminator_unknown_type() -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz({**mcq(), "type": "essay"}))


def test_discriminator_selects_model_errors() -> None:
    # A numerical-typed item missing key_code must fail as numerical, not mcq.
    bad = num()
    del bad["key_code"]
    with pytest.raises(ValidationError, match="key_code"):
        parse_quiz(quiz(bad))


def test_json_schema() -> None:
    schema = quiz_json_schema()
    assert schema["title"] == "Quiz"
    assert "items" in schema["properties"]


# ---- common fields / Quiz bounds -----------------------------------------


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        parse_quiz(quiz(mcq(surprise=1)))
    with pytest.raises(ValidationError, match="extra"):
        parse_quiz({**quiz(mcq()), "surprise": 1})


@pytest.mark.parametrize("topic", ["", "x" * 81])
def test_topic_length(topic: str) -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz(mcq(topic=topic)))


def test_too_many_tags() -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz(mcq(tags=[f"t{i}" for i in range(9)])))
    parse_quiz(quiz(mcq(tags=[f"t{i}" for i in range(8)])))


def test_quiz_item_count_bounds() -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz())
    with pytest.raises(ValidationError):
        parse_quiz(quiz(*[subj() for _ in range(21)]))
    parse_quiz(quiz(*[subj() for _ in range(20)]))


# ---- MCQ ------------------------------------------------------------------


@pytest.mark.parametrize("n", [3, 5])
def test_mcq_wrong_option_count(n: int) -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz(mcq(options=[f"o{i}" for i in range(n)])))


def test_mcq_duplicate_options() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        parse_quiz(quiz(mcq(options=["A", "B", "B", "C"])))


def test_mcq_blank_option() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        parse_quiz(quiz(mcq(options=["A", "B", "  ", "C"])))


@pytest.mark.parametrize("idx", [-1, 4])
def test_mcq_correct_index_range(idx: int) -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz(mcq(correct_index=idx)))


@pytest.mark.parametrize(
    "miscon",
    [
        {1: "a", 2: "b"},  # missing one
        {0: "a", 1: "b", 2: "c"},  # includes the correct index
        {1: "a", 2: "b", 3: "c", 0: "d"},  # four keys
        {1: "a", 2: "b", 3: ""},  # empty explanation
    ],
)
def test_mcq_misconception_keys(miscon: dict[int, str]) -> None:
    with pytest.raises(ValidationError, match="misconceptions"):
        parse_quiz(quiz(mcq(misconceptions=miscon)))


# ---- Numerical ------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "x = 1",
        "import os\nresult = 1",
        "import sys\nresult = 1",
        "f = open('a')\nresult = 1",
        "__import__('os')\nresult = 1",
        "result = eval('1')",
        "exec('x=1')\nresult = 1",
    ],
)
def test_key_code_lint(code: str) -> None:
    with pytest.raises(ValidationError, match="key_code"):
        parse_quiz(quiz(num(key_code=code)))


@pytest.mark.parametrize("tol", [0, -0.1, 0.11, 1.0])
def test_tolerance_out_of_range(tol: float) -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz(num(tolerance_rel=tol)))


def test_tolerance_upper_bound_ok() -> None:
    parse_quiz(quiz(num(tolerance_rel=0.1)))


@pytest.mark.parametrize(
    "ws", ["Q = {1abc}", "Q = {a b}", "Q = {}", "Q = {a.b}", "Q = {a:.2f}"]
)
def test_bad_placeholder(ws: str) -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        parse_quiz(quiz(num(worked_solution=ws)))


def test_unbalanced_brace() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        parse_quiz(quiz(num(worked_solution="Q = {answer")))


@pytest.mark.parametrize(
    "ws",
    [
        "Q = 3.5 m3/s",
        "Q is 11 m3/s",
        "Q is 1,000",
        "Q is 12",
        "Q is 1e5",
        "Q is 0.5",
        "Q is 007",
        "Q = {answer} at 25 C",
    ],
)
def test_digits_in_worked_solution(ws: str) -> None:
    with pytest.raises(ValidationError, match="digits"):
        parse_quiz(quiz(num(worked_solution=ws)))


@pytest.mark.parametrize(
    "ws",
    [
        "Step 1. Use C_A0 and x2 to get {answer}.",
        "Take 0 to 10 tanks; with 10 of them X is {answer}.",
        "Step 3: {v_flow} then 5.",
        "Q = {answer} {C_A0}",
    ],
)
def test_allowed_worked_solution(ws: str) -> None:
    parse_quiz(quiz(num(worked_solution=ws)))


# ---- Subjective -----------------------------------------------------------


@pytest.mark.parametrize(
    "rubric", [[], [""], ["ok", " "], [f"c{i}" for i in range(11)]]
)
def test_rubric_bounds(rubric: list[str]) -> None:
    with pytest.raises(ValidationError):
        parse_quiz(quiz(subj(rubric=rubric)))


# ---- check_key ------------------------------------------------------------


def item(unit: str = "m", tol: float = 0.01) -> NumericalItem:
    parsed = parse_quiz(quiz(num(unit=unit, tolerance_rel=tol))).items[0]
    assert isinstance(parsed, NumericalItem)
    return parsed


def res(a: Any = 10.0, c: Any = 10.0, ua: Any = "m", uc: Any = "m") -> dict[str, Any]:
    return {
        "answer": {"value": a, "unit": ua},
        "check": {"value": c, "unit": uc, "method": "other"},
    }


def test_check_key_ok() -> None:
    assert check_key(res(10.0, 10.05), item()) == KeyCheck(True, 10.0, None)


def test_check_key_ok_int_and_strip() -> None:
    assert check_key(res(10, 10, " m ", "m "), item()).ok


def test_keycheck_frozen() -> None:
    with pytest.raises(AttributeError):
        KeyCheck(True, 1.0, None).ok = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (None, "not_a_dict"),
        ([1], "not_a_dict"),
        ("x", "not_a_dict"),
        ({"check": {"value": 1.0, "unit": "m"}}, "missing_answer"),
        ({"answer": 5, "check": {"value": 1.0, "unit": "m"}}, "missing_answer"),
        ({"answer": {"value": 1.0, "unit": "m"}}, "missing_check"),
        ({"answer": {"value": 1.0, "unit": "m"}, "check": "x"}, "missing_check"),
        (res(a="10.0"), "not_a_number"),
        (res(c="10.0"), "not_a_number"),
        (res(a=True), "not_a_number"),
        (res(c=False), "not_a_number"),
        (res(a=None), "not_a_number"),
        (res(a=float("nan")), "not_a_number"),
        (res(c=float("inf")), "not_a_number"),
        (
            {"answer": {"unit": "m"}, "check": {"value": 1.0, "unit": "m"}},
            "not_a_number",
        ),
        (res(ua="km"), "unit_mismatch"),
        (res(uc="s"), "unit_mismatch"),
        (res(ua=None), "unit_mismatch"),
        (
            {"answer": {"value": 1.0}, "check": {"value": 1.0, "unit": "m"}},
            "unit_mismatch",
        ),
        (res(10.0, 11.0), "methods_disagree"),
        (res(10.0, 9.0), "methods_disagree"),
    ],
)
def test_check_key_reasons(result: object, reason: str) -> None:
    out = check_key(result, item())
    assert out == KeyCheck(False, None, reason)


def test_check_key_tolerance_boundary() -> None:
    assert check_key(res(100.0, 101.0), item(tol=0.01)).ok
    assert not check_key(res(100.0, 101.5), item(tol=0.01)).ok
    assert check_key(res(100.0, 110.0), item(tol=0.1)).ok


def test_check_key_zero_answer_absolute() -> None:
    assert check_key(res(0.0, 1e-13), item()).ok
    assert not check_key(res(0.0, 1e-6), item()).ok


def test_check_key_negative_answer() -> None:
    assert check_key(res(-10.0, -10.05), item()).ok
    assert check_key(res(-10.0, -10.05), item()).value == -10.0


# ---- fill_solution --------------------------------------------------------


def numerical(ws: str) -> NumericalItem:
    parsed = parse_quiz(quiz(num(worked_solution=ws))).items[0]
    assert isinstance(parsed, NumericalItem)
    return parsed


def test_fill_answer_and_check_four_sig_figs() -> None:
    out = fill_solution(numerical("A={answer} C={check}"), res(2 / 3, 0.123456))
    assert out == "A=0.6667 C=0.1235"


def test_fill_values_and_top_level() -> None:
    result = res(1234567.0, 1.0)
    result["values"] = {"v_flow": {"value": 0.5, "unit": "m3/s"}}
    result["extra"] = 42
    out = fill_solution(numerical("{answer} {v_flow} {extra}"), result)
    assert out == "1.235e+06 0.5 42"


def test_fill_values_take_priority_over_top_level() -> None:
    result = res()
    result["values"] = {"q": {"value": 1.0}}
    result["q"] = 2.0
    assert fill_solution(numerical("{q}"), result) == "1"


def test_fill_repeated_placeholder() -> None:
    assert (
        fill_solution(numerical("{answer} then {answer}"), res(2.0, 2.0)) == "2 then 2"
    )


@pytest.mark.parametrize("name", ["missing", "answer_x"])
def test_fill_missing_raises(name: str) -> None:
    with pytest.raises(KeyError):
        fill_solution(numerical("{" + name + "}"), res())


def test_fill_non_numeric_value_raises() -> None:
    result = res()
    result["values"] = {"q": {"value": "3"}}
    with pytest.raises(KeyError):
        fill_solution(numerical("{q}"), result)
    result2 = res()
    result2["flag"] = True
    with pytest.raises(KeyError):
        fill_solution(numerical("{flag}"), result2)


def test_fill_answer_missing_raises() -> None:
    with pytest.raises(KeyError):
        fill_solution(numerical("{answer}"), {})


# ---- mock fixture ---------------------------------------------------------


def test_mock_fixture_round_trip() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    q = parse_quiz(text)
    assert len(q.items) == 4
    assert [i.type for i in q.items] == ["mcq", "mcq", "numerical", "subjective"]
    again = parse_quiz(q.model_dump_json())
    assert again == q


def test_mock_numerical_key_runs_and_checks() -> None:
    q = parse_quiz(FIXTURE.read_text(encoding="utf-8"))
    item_ = next(i for i in q.items if isinstance(i, NumericalItem))
    ns: dict[str, Any] = {}
    exec(item_.key_code, ns)  # noqa: S102  (tests only; never server code)
    result = ns["result"]
    verdict = check_key(result, item_)
    assert verdict.ok
    assert verdict.value is not None
    assert math.isclose(verdict.value, 2 / 3)
    text = fill_solution(item_, result)
    assert "{" not in text
    assert "0.6667" in text
    assert "2" in text
