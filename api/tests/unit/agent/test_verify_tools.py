import base64
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
from app.agent.verify import MAX_STDOUT, clean, flat_numbers, verify

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
        ({"answer": {"value": 2.0, "unit": ""}, "check": OK["check"]}, "answer"),
        ({"answer": OK["answer"]}, "check"),
        ({**OK, "check": {"value": 2.0, "unit": "cm"}}, "unit"),
        ({**OK, "values": {"v": {"value": "1"}}}, "values"),
    ],
)
def test_verify_rejects_bad_shapes(result: Any, reason: str) -> None:
    v = verify(result)
    assert not v.ok and reason in (v.reason or "") and not v.disagree


def test_verify_flags_disagreement() -> None:
    v = verify({**OK, "check": {"value": 2.1, "unit": "m"}})
    assert (v.ok, v.disagree) == (False, True)


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
