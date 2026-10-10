import asyncio
import base64
import json
from typing import Any

import pytest
from pydantic import BaseModel

from app.agent import loop
from app.agent.loop import Deps
from app.agent.state import InMemoryStore, SolveNotFound
from app.agent.steps import ResultBody
from app.agent.tools import Hit, StubTools
from app.llm.client import LLMResult, ToolCall
from app.llm.errors import ModelUnavailable

USER = "u1"
GOOD = {
    "answer": {"value": 0.6667, "unit": "-"},
    "check": {"value": 0.66671, "unit": "-", "method": "numeric"},
    "values": {"k": {"value": 0.25, "unit": "1/min"}},
}
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()


def res(text: str = "", calls: list[ToolCall] | None = None) -> LLMResult:
    return LLMResult(text, None, calls or [], "m", "r", 0.001, 1)


def tool(name: str, **args: Any) -> LLMResult:
    return res(calls=[ToolCall(f"c-{name}", name, json.dumps(args))])


class FakeLLM:
    """Plays back a script of (method, reply) and records every call."""

    def __init__(self, *script: tuple[str, Any]) -> None:
        self.script = list(script)
        self.calls: list[tuple[str, str, list[dict[str, Any]]]] = []

    def _next(self, method: str, role: str, messages: list[dict[str, Any]]) -> Any:
        self.calls.append((method, role, json.loads(json.dumps(messages))))
        want, reply = self.script.pop(0)
        assert want == method, f"expected {want}, got {method}"
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def chat(self, role: str, messages: Any, **kw: Any) -> LLMResult:
        r: LLMResult = self._next("chat", role, messages)
        return r

    async def chat_tools(
        self, role: str, messages: Any, tools: Any, **kw: Any
    ) -> LLMResult:
        r: LLMResult = self._next("chat_tools", role, messages)
        return r

    async def chat_json[T: BaseModel](
        self, role: str, messages: Any, schema: type[T], **kw: Any
    ) -> tuple[T, LLMResult]:
        return schema.model_validate(self._next("chat_json", role, messages)), res()


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Notes(StubTools):
    async def search_my_notes(self, user_id: str, query: str) -> list[Hit]:
        return [Hit("Lecture 4: CSTR", "Da = k tau", "https://notes/4")]


def deps(llm: FakeLLM, **kw: Any) -> Deps:
    return Deps(llm=llm, store=InMemoryStore(), clock=kw.pop("clock", Clock()), **kw)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def solve(
    d: Deps, *bodies: dict[str, Any], question: str = "Find X"
) -> list[dict[str, Any]]:
    sid, step = await loop.start(question, d, user_id=USER)
    steps = [step]
    for body in bodies:
        steps.append(await loop.on_result(sid, USER, ResultBody(**body), d))
    return steps


def calc(*after: tuple[str, Any]) -> FakeLLM:
    return FakeLLM(("chat_json", {"kind": "calc"}), *after)


def test_calc_happy_path() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="result = {}")),
        ("chat_json", {"answer_md": "X = 0.6667"}),
    )
    d = deps(llm, tools=Notes())
    steps = run(solve(d, {"result": GOOD, "figures": [PNG]}))
    assert steps[0] == {"type": "run_python", "code": "result = {}", "timeout_s": 10}
    final = steps[1]
    assert final["type"] == "final"
    assert final["confidence"] == "high"
    assert final["numbers"] == {"answer": 0.6667, "check": 0.66671, "k (1/min)": 0.25}
    assert final["figures"] == ["data:image/png;base64," + PNG]
    assert final["sources"] == [{"title": "Lecture 4: CSTR", "url": "https://notes/4"}]
    assert "diagram_mermaid" not in final
    # notes reach the solver as quoted data; the run is reported on the tool call
    assert "quoted data" in llm.calls[1][2][0]["content"]
    assert "Lecture 4" in llm.calls[1][2][0]["content"]


def test_fenced_code_is_the_fallback() -> None:
    llm = calc(("chat_tools", res("Plan:\n```python\nresult = {}\n```")))
    steps = run(solve(deps(llm)))
    assert steps[0]["code"] == "result = {}"


def test_concept_question_has_no_code_and_no_numbers() -> None:
    llm = FakeLLM(("chat_json", {"kind": "concept"}), ("chat", res("A CSTR is ...")))
    final = run(solve(deps(llm)))[0]
    assert final["type"] == "final"
    assert (final["confidence"], final["numbers"]) == ("medium", {})


def test_upload_needs_confirmation_first() -> None:
    async def read(upload_id: str) -> str:
        return "A 2 m^3 CSTR ..."

    d = deps(FakeLLM(), read_upload=read)
    sid, step = run(loop.start("", d, user_id=USER, upload_id="up1"))
    assert step == {"type": "need_confirm", "extracted_text": "A 2 m^3 CSTR ..."}
    assert run(loop.get_step(sid, USER, d)) == step


def test_sandbox_error_goes_back_to_the_model() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="1/0")),
        ("chat_tools", tool("run_python", code="result = {}")),
        ("chat_json", {"answer_md": "ok"}),
    )
    steps = run(solve(deps(llm), {"error": "ZeroDivisionError"}, {"result": GOOD}))
    assert steps[1]["code"] == "result = {}"
    told = llm.calls[2][2][-1]
    assert told["role"] == "tool" and "ZeroDivisionError" in told["content"]
    assert steps[2]["confidence"] == "high"


def test_shape_failure_is_explained_to_the_model() -> None:
    bad = {"answer": {"value": "0.67", "unit": "-"}, "check": GOOD["check"]}
    llm = calc(
        ("chat_tools", tool("run_python", code="a")),
        ("chat_tools", tool("run_python", code="b")),
        ("chat_json", {"answer_md": "ok"}),
    )
    steps = run(solve(deps(llm), {"result": bad}, {"result": GOOD}))
    assert "Check failed" in llm.calls[2][2][-1]["content"]
    assert steps[2]["confidence"] == "high"


def disagreeing(answer: float = 0.6667) -> dict[str, Any]:
    return {
        "answer": {"value": answer, "unit": "-"},
        "check": {"value": 0.5, "unit": "-", "method": "numeric"},
    }


def test_disagreeing_methods_trigger_one_cross_check_that_agrees() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="a")),
        ("chat_tools", tool("run_python", code="b")),
        ("chat_json", {"answer_md": "ok"}),
    )
    steps = run(solve(deps(llm), {"result": disagreeing()}, {"result": GOOD}))
    assert llm.calls[2][1] == "cross_check"
    assert steps[2]["confidence"] == "medium"


def test_cross_check_that_disagrees_is_flagged_low() -> None:
    other = {
        **GOOD,
        "answer": {"value": 0.9, "unit": "-"},
        "check": {"value": 0.9, "unit": "-"},
    }
    llm = calc(
        ("chat_tools", tool("run_python", code="a")),
        ("chat_tools", tool("run_python", code="b")),
        ("chat_json", {"answer_md": "ok"}),
    )
    steps = run(solve(deps(llm), {"result": disagreeing()}, {"result": other}))
    assert steps[2]["confidence"] == "low"


def test_at_most_four_tool_steps() -> None:
    llm = calc(*[("chat_tools", tool("run_python", code="x")) for _ in range(4)])
    errors = [{"error": "boom"}] * 4
    steps = run(solve(deps(llm), *errors))
    assert len(llm.calls) == 5  # classify + 4 tool steps, no fifth model call
    assert steps[-1]["type"] == "final"
    assert steps[-1]["confidence"] == "low"
    assert steps[-1]["numbers"] == {}


def test_ninety_second_budget() -> None:
    clock = Clock()
    llm = calc(("chat_tools", tool("run_python", code="x")))
    d = deps(llm, clock=clock)
    sid, _ = run(loop.start("q", d, user_id=USER))
    clock.now = 91.0
    final = run(loop.on_result(sid, USER, ResultBody(error="slow"), d))
    assert final["confidence"] == "low"
    assert len(llm.calls) == 2


def test_unknown_tool_is_refused_and_counted() -> None:
    llm = calc(
        ("chat_tools", tool("shell", cmd="ls")),
        ("chat_tools", tool("run_python", code="result = {}")),
    )
    steps = run(solve(deps(llm)))
    refused = llm.calls[2][2][-1]
    assert refused["role"] == "tool" and refused["content"].startswith(
        "refused: unknown tool"
    )
    assert steps[0]["type"] == "run_python"


def test_diagram_is_attached() -> None:
    llm = calc(
        ("chat_tools", tool("draw_diagram", mermaid="flowchart LR\n A-->B")),
        ("chat_tools", tool("run_python", code="r")),
        ("chat_json", {"answer_md": "ok"}),
    )
    final = run(solve(deps(llm), {"result": GOOD}))[1]
    assert final["diagram_mermaid"] == "flowchart LR\n A-->B"


def test_result_after_the_final_returns_the_final_again() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="r")),
        ("chat_json", {"answer_md": "ok"}),
    )
    d = deps(llm)
    sid, _ = run(loop.start("q", d, user_id=USER))
    body = ResultBody(result=GOOD)
    first = run(loop.on_result(sid, USER, body, d))
    again = run(loop.on_result(sid, USER, body, d))
    assert first == again and first["type"] == "final"
    assert len(llm.calls) == 3


def test_identical_failing_runs_are_not_mistaken_for_retries() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="x")),
        ("chat_tools", tool("run_python", code="x")),
        ("chat_tools", tool("run_python", code="y")),
    )
    steps = run(solve(deps(llm), {"error": "boom"}, {"error": "boom"}))
    assert steps[-1]["code"] == "y"


def test_other_users_solve_is_not_found() -> None:
    llm = calc(("chat_tools", tool("run_python", code="r")))
    d = deps(llm)
    sid, _ = run(loop.start("q", d, user_id=USER))
    with pytest.raises(SolveNotFound):
        run(loop.on_result(sid, "someone-else", ResultBody(result=GOOD), d))
    with pytest.raises(SolveNotFound):
        run(loop.get_step(sid, "someone-else", d))


def test_model_unavailable_is_a_low_confidence_final() -> None:
    llm = FakeLLM(("chat_json", ModelUnavailable("down")))
    final = run(solve(deps(llm)))[0]
    assert final["type"] == "final"
    assert final["confidence"] == "low"


def guard_flags(*bad_runs: list[str]) -> Any:
    runs = list(bad_runs)

    def guard(answer_md: str, result: Any, question: str) -> list[str]:
        return runs.pop(0)

    return guard


def test_guardrail_regenerates_once_then_flags() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="r")),
        ("chat_json", {"answer_md": "X = 0.7"}),
        ("chat_json", {"answer_md": "X = 0.71"}),
    )
    d = deps(llm, guard=guard_flags(["0.7"], ["0.71"]))
    final = run(solve(d, {"result": GOOD}))[1]
    assert "0.7" in llm.calls[3][2][-1]["content"]
    assert final["confidence"] == "low"


def test_guardrail_regeneration_that_fixes_it_stays_high() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="r")),
        ("chat_json", {"answer_md": "X = 0.7"}),
        ("chat_json", {"answer_md": "X = 0.6667"}),
    )
    d = deps(llm, guard=guard_flags(["0.7"], []))
    final = run(solve(d, {"result": GOOD}))[1]
    assert (final["answer_md"], final["confidence"]) == ("X = 0.6667", "high")


def test_flag_only_mode_does_not_regenerate() -> None:
    llm = calc(
        ("chat_tools", tool("run_python", code="r")),
        ("chat_json", {"answer_md": "X = 0.7"}),
    )
    d = deps(llm, guard=guard_flags(["0.7"]), regenerate_on_flag=False)
    final = run(solve(d, {"result": GOOD}))[1]
    assert final["confidence"] == "low"
    assert len(llm.calls) == 3


def test_state_is_saved_after_every_step() -> None:
    llm = calc(("chat_tools", tool("run_python", code="r")))
    d = deps(llm)
    sid, step = run(loop.start("q", d, user_id=USER))
    assert isinstance(d.store, InMemoryStore)
    saved = d.store.states[sid]
    assert (saved.status, saved.last_step, saved.steps_used) == (
        "awaiting_result",
        step,
        1,
    )


def test_two_failed_checks_switch_to_the_cross_check_model() -> None:
    bad = {"answer": {"value": "0.67", "unit": "-"}, "check": GOOD["check"]}
    llm = calc(
        ("chat_tools", tool("run_python", code="a")),
        ("chat_tools", tool("run_python", code="b")),
        ("chat_tools", tool("run_python", code="c")),
        ("chat_json", {"answer_md": "ok"}),
    )
    steps = run(solve(deps(llm), {"result": bad}, {"result": bad}, {"result": GOOD}))
    assert [c[1] for c in llm.calls[1:4]] == ["solver", "solver", "cross_check"]
    assert steps[-1]["confidence"] == "medium"
