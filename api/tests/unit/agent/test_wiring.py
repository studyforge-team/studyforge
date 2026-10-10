"""The full calc pipeline with B8, CH3 and C2 wired in, with a scripted model.

The template code the loop emits is executed here with our own chemlab package,
standing in for the browser worker. That is test-only and runs our golden-tested
template, never model-written code."""

import asyncio
from typing import Any

from chemlab import cstr, mccabe, pfr
from test_loop import GOOD, Clock, FakeLLM, res, tool

from app.agent import loop
from app.agent.loop import Deps, b8_guard
from app.agent.read_question import upload_reader
from app.agent.state import InMemoryStore
from app.agent.steps import ResultBody
from app.llm.errors import ModelUnavailable

USER = "u1"
SPECS = {"cstr": cstr.SPEC, "pfr": pfr.SPEC, "mccabe": mccabe.SPEC}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def browser(code: str) -> ResultBody:
    """Stand-in for the Pyodide worker running a server-built template step."""
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102 - test only, our own template code
    return ResultBody(result=namespace["result"], ms=5)


def deps(llm: FakeLLM, **kw: Any) -> Deps:
    return Deps(llm=llm, store=InMemoryStore(), clock=Clock(), templates=SPECS, **kw)


def pfr_pick() -> dict[str, Any]:
    return {
        "template": "pfr",
        "inputs": {
            "k": {"value": 0.6, "unit": "1/min"},
            "V": {"value": 200, "unit": "L"},
            "v0": {"value": 1, "unit": "L/s"},
            "n": {"value": 1, "unit": "-"},
        },
    }


def test_template_question_runs_the_template_once() -> None:
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_json", pfr_pick()),
        ("chat_json", {"answer_md": "The conversion is X = 0.8647 (86.47 %)."}),
    )
    d = deps(llm)
    sid, step = run(loop.start("First-order PFR, k = 0.6 1/min, ...", d, user_id=USER))
    assert step["type"] == "run_python"
    assert step["code"].startswith("from chemlab.pfr import run\n")
    final = run(loop.on_result(sid, USER, browser(step["code"]), d))
    assert final["type"] == "final"
    assert final["confidence"] == "high"  # template is golden-tested, B8 clean
    assert abs(final["numbers"]["X"] - 0.8647) < 1e-3
    assert "X_percent (%)" in final["numbers"]
    # router (classify), router (pick), solver (explain): no tool-step model call
    assert [c[1] for c in llm.calls] == ["router", "router", "solver"]


def test_steady_states_reach_the_explanation_and_the_guardrail() -> None:
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_json", {"template": "cstr", "inputs": {}}),  # the defaults: 3 states
        ("chat_json", {"answer_md": "Three steady states: 301.3 K, 348.6 K, 391.3 K."}),
    )
    d = deps(llm)
    sid, step = run(loop.start("adiabatic CSTR ...", d, user_id=USER))
    final = run(loop.on_result(sid, USER, browser(step["code"]), d))
    assert final["confidence"] == "high"
    explain_input = llm.calls[2][2][-1]["content"]
    assert "steady_states" in explain_input and '"stable": false' in explain_input


def test_template_that_cannot_answer_hands_over_to_the_solver() -> None:
    bad = pfr_pick()
    bad["inputs"]["V"] = {"value": 1e9, "unit": "m^3"}  # out of range -> no template
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_json", bad),
        ("chat_tools", tool("run_python", code="result = {}")),
    )
    step = run(loop.start("q", deps(llm), user_id=USER))[1]
    assert step["code"] == "result = {}"  # general solver, template skipped


def test_template_error_result_falls_back_with_the_reason() -> None:
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_json", pfr_pick()),
        ("chat_tools", tool("run_python", code="result = {}")),
    )
    d = deps(llm)
    sid, _ = run(loop.start("q", d, user_id=USER))
    failed = ResultBody(result={"ok": False, "errors": [{"code": "no_steady_state"}]})
    step = run(loop.on_result(sid, USER, failed, d))
    assert step == {"type": "run_python", "code": "result = {}", "timeout_s": 10}
    told = llm.calls[2][2][-1]["content"]
    assert "pfr template could not answer" in told and "no_steady_state" in told


def test_guardrail_is_on_by_default_and_catches_an_invented_number() -> None:
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_tools", tool("run_python", code="r")),
        ("chat_json", {"answer_md": "X = 0.6667, so about 73 % reacts."}),
        ("chat_json", {"answer_md": "X = 0.6667."}),
    )
    d = Deps(llm=llm, store=InMemoryStore(), clock=Clock())
    assert d.guard is b8_guard
    sid, _ = run(loop.start("Find X", d, user_id=USER))
    final = run(loop.on_result(sid, USER, ResultBody(result=GOOD), d))
    assert "73" in llm.calls[3][2][-1]["content"]  # regenerate names the bad number
    assert (final["answer_md"], final["confidence"]) == ("X = 0.6667.", "high")


def test_b8_guard_allows_result_and_question_numbers() -> None:
    assert b8_guard("k = 0.25 1/min gives X = 0.6667", GOOD, "k is 0.25") == []
    assert b8_guard("X = 0.9", GOOD, "q") == ["0.9"]


class FakeVision:
    def __init__(self, reply: Any) -> None:
        self.reply = reply

    async def vision(self, image_url: str, prompt: str, **kw: Any) -> Any:
        if isinstance(self.reply, Exception):
            raise self.reply
        return res(self.reply)


def png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, "PNG")
    return buf.getvalue()


def test_upload_reader_formats_the_confirm_text() -> None:
    async def fetch(upload_id: str) -> tuple[bytes, str]:
        return png(), "image/png"

    reply = (
        '{"text": "Find V for the CSTR.", "latex": "X = 0.9", '
        '"figure_description": "a tank", "confidence": "high"}'
    )
    read = upload_reader(fetch, FakeVision(reply))
    text = run(read("up1"))
    assert text == "Find V for the CSTR.\n\n$$\nX = 0.9\n$$\n\nFigure: a tank"


def test_unreadable_upload_lets_the_student_type_instead() -> None:
    async def missing(upload_id: str) -> tuple[bytes, str]:
        raise KeyError(upload_id)

    async def fetch(upload_id: str) -> tuple[bytes, str]:
        return png(), "image/png"

    assert run(upload_reader(missing, FakeVision("{}"))("x")) == ""
    assert run(upload_reader(fetch, FakeVision(ModelUnavailable("down")))("x")) == ""

    async def text_only(upload_id: str) -> tuple[bytes, str]:
        return b"hello", "text/plain"

    assert run(upload_reader(text_only, FakeVision("{}"))("x")) == ""


def test_photo_question_goes_through_confirm_then_solves() -> None:
    async def fetch(upload_id: str) -> tuple[bytes, str]:
        return png(), "image/png"

    reply = '{"text": "Q", "latex": "", "figure_description": "", "confidence": "high"}'
    llm = FakeLLM(("chat_json", {"kind": "concept"}), ("chat", res("Answer")))
    d = deps(llm, read_upload=upload_reader(fetch, FakeVision(reply)))
    step = run(loop.start("", d, user_id=USER, upload_id="up1"))[1]
    assert step == {"type": "need_confirm", "extracted_text": "Q"}
    final = run(
        loop.start("Q (edited)", d, user_id=USER, upload_id="up1", confirmed=True)
    )[1]
    assert final["type"] == "final"
