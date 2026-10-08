import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.agent import loop
from app.agent.loop import Deps
from app.agent.smoke import (
    NodeRunner,
    Problem,
    RunnerUnavailable,
    load_problems,
    run_suite,
    score,
    solve_one,
)
from app.agent.state import InMemoryStore
from app.agent.steps import ResultBody
from app.llm.client import LLMResult, ToolCall


def res(text: str = "", calls: list[ToolCall] | None = None) -> LLMResult:
    return LLMResult(text, None, calls or [], "m", "r", 0.01, 1)


def run_py(code: str) -> LLMResult:
    return res(calls=[ToolCall("c1", "run_python", json.dumps({"code": code}))])


class FakeLLM:
    """Plays back a script of (method, reply)."""

    def __init__(self, *script: tuple[str, Any]) -> None:
        self.script = list(script)

    def _next(self, method: str) -> Any:
        want, reply = self.script.pop(0)
        assert want == method, f"expected {want}, got {method}"
        return reply

    async def chat(self, role: str, messages: Any, **kw: Any) -> LLMResult:
        r: LLMResult = self._next("chat")
        return r

    async def chat_tools(
        self, role: str, messages: Any, tools: Any, **kw: Any
    ) -> LLMResult:
        r: LLMResult = self._next("chat_tools")
        return r

    async def chat_json[T: BaseModel](
        self, role: str, messages: Any, schema: type[T], **kw: Any
    ) -> tuple[T, LLMResult]:
        return schema.model_validate(self._next("chat_json")), res()


class Tick:
    """A clock that advances 1 s per reading."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


class FakeRunner:
    """Returns a canned ResultBody per code string and records the calls."""

    def __init__(self, bodies: dict[str, ResultBody]) -> None:
        self.bodies = bodies
        self.calls: list[tuple[str, float]] = []

    async def run(self, code: str, timeout_s: float) -> ResultBody:
        self.calls.append((code, timeout_s))
        return self.bodies[code]


def answer_body(value: float, unit: str) -> ResultBody:
    return ResultBody(
        result={
            "answer": {"value": value, "unit": unit},
            "check": {"value": value, "unit": unit, "method": "numeric"},
        }
    )


def calc_script(code: str, text: str = "done") -> list[tuple[str, Any]]:
    return [
        ("chat_json", {"kind": "calc"}),
        ("chat_tools", run_py(code)),
        ("chat_json", {"answer_md": text}),
    ]


def problem(pid: str, value: float, unit: str, tol: float = 0.01) -> Problem:
    return Problem(
        id=pid,
        question=f"q {pid}",
        answer={"value": value, "unit": unit},  # type: ignore[arg-type]
        tolerance_rel=tol,
    )


def final(numbers: dict[str, float], confidence: str = "high") -> dict[str, Any]:
    return {
        "type": "final",
        "answer_md": "x",
        "numbers": numbers,
        "confidence": confidence,
    }


# ---- scoring ----


def test_score_correct_and_tolerance_boundary() -> None:
    p = problem("a", 100.0, "min")
    assert score(p, final({"answer (min)": 101.0})) == (True, 101.0, "answer (min)")
    assert score(p, final({"answer (min)": 99.0}))[0] is True
    assert score(p, final({"answer (min)": 101.01}))[0] is False
    assert score(p, final({"answer (min)": 98.9}))[0] is False


def test_score_unit_mismatch_is_wrong() -> None:
    p = problem("a", 52.15, "kPa")
    assert score(p, final({"answer (Pa)": 52.15})) == (False, 52.15, "answer (Pa)")


def test_score_unit_normalisation_and_bare_answer() -> None:
    p = problem("a", 2.0, "m^3")
    assert score(p, final({"answer (m**3)": 2.0}))[0] is True
    assert score(p, final({"answer ( m ^ 3 )": 2.0}))[0] is True
    assert score(p, final({"answer": 2.0}))[0] is True  # no unit in the key


def test_score_ignores_check_and_other_keys() -> None:
    p = problem("a", 5.0, "mol")
    assert score(p, final({"check (mol)": 5.0, "k": 5.0})) == (False, None, None)
    assert score(p, final({"check (mol)": 1.0, "answer (mol)": 5.0}))[0] is True


def test_score_prefers_plain_answer_key() -> None:
    p = problem("a", 5.0, "-")
    assert score(p, final({"answer (zz)": 1.0, "answer": 5.0}))[0] is True


# ---- solve_one ----


def deps_for(llm: FakeLLM) -> Deps:
    return Deps(llm=llm, store=InMemoryStore(), clock=Tick())


def test_solve_one_counts_runs_after_an_error() -> None:
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_tools", run_py("bad")),
        ("chat_tools", run_py("good")),
        ("chat_json", {"answer_md": "ok"}),
    )
    runner = FakeRunner(
        {"bad": ResultBody(error="NameError: x"), "good": answer_body(10.0, "min")}
    )
    out = asyncio.run(solve_one(problem("a", 10.0, "min"), deps_for(llm), runner))
    assert out.runs == 2
    assert out.error is None
    assert out.final is not None and out.final["confidence"] == "high"
    assert out.confidence == "high"
    assert out.cost_usd == pytest.approx(0.04)  # router + 2 solver + explain
    assert out.seconds > 0
    assert [c[0] for c in runner.calls] == ["bad", "good"]
    assert runner.calls[0][1] == 10


def test_solve_one_need_confirm_is_an_error_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = loop.start

    async def start(q: str, deps: Deps, *, user_id: str) -> Any:
        return await real(q, deps, user_id=user_id, upload_id="u1")

    async def read_upload(upload_id: str) -> str:
        return "text read from the upload"

    monkeypatch.setattr(loop, "start", start)
    d = deps_for(FakeLLM())
    d.read_upload = read_upload
    out = asyncio.run(solve_one(problem("a", 1, "-"), d, FakeRunner({})))
    assert out.final is None
    assert out.error == "need_confirm"
    assert out.runs == 0


def test_solve_one_stops_at_max_runs() -> None:
    llm = FakeLLM(
        ("chat_json", {"kind": "calc"}),
        ("chat_tools", run_py("bad")),
        ("chat_tools", run_py("bad")),
        ("chat_tools", run_py("bad")),  # the loop asks again after the 2nd run
    )
    runner = FakeRunner({"bad": ResultBody(error="boom")})
    out = asyncio.run(
        solve_one(problem("a", 1, "-"), deps_for(llm), runner, max_runs=2)
    )
    assert out.runs == 2
    assert out.final is None
    assert out.error == "max_runs"


# ---- suite and report ----


def abstaining_script() -> list[tuple[str, Any]]:
    # the model never produces code: the loop runs out of steps and abstains
    return [("chat_json", {"kind": "calc"})] + [("chat_tools", res("no code"))] * 4


def test_run_suite_totals_and_markdown() -> None:
    llms = iter(
        [
            FakeLLM(*calc_script("c")),
            FakeLLM(*calc_script("w")),
            FakeLLM(*abstaining_script()),
        ]
    )
    runner = FakeRunner({"c": answer_body(10.0, "min"), "w": answer_body(99.0, "min")})
    problems = [
        problem("P-1", 10.0, "min"),
        problem("P-2", 10.0, "min"),
        problem("P-3", 10.0, "min"),
    ]
    report = asyncio.run(run_suite(problems, lambda: deps_for(next(llms)), runner))
    assert [r.status for r in report.rows] == ["correct", "wrong", "abstained"]
    assert report.total == 3
    assert report.correct == 1
    assert report.abstained == 1
    assert report.wrong_numbers == 1
    assert report.errors == 0
    assert report.total_cost == pytest.approx(0.03 + 0.03 + 0.05)
    assert report.median_seconds > 0
    assert report.passed(0.3) and not report.passed(0.4)
    assert report.passed(0.3, max_median_s=1e6)
    assert not report.passed(0.3, max_median_s=0.0)
    md = report.to_markdown()
    assert "1/3" in md
    assert "| P-1 | correct |" in md
    assert "| P-2 | wrong |" in md
    assert "| P-3 | abstained |" in md
    assert "abstained: 1" in md and "wrong numbers: 1" in md


def test_report_empty_never_passes() -> None:
    report = asyncio.run(run_suite([], lambda: deps_for(FakeLLM()), FakeRunner({})))
    assert report.total == 0
    assert not report.passed(0.0)
    assert report.median_seconds == 0.0


# ---- NodeRunner ----


class FakeProc:
    def __init__(
        self, out: bytes = b"", err: bytes = b"", code: int = 0, hang: bool = False
    ) -> None:
        self.out, self.err, self.returncode, self.hang = out, err, code, hang
        self.stdin_data: bytes | None = None
        self.killed = False

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        self.stdin_data = input
        if self.hang:
            await asyncio.sleep(3600)
        return self.out, self.err

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode or 0


class Spawner:
    def __init__(self, proc: FakeProc | Exception) -> None:
        self.proc = proc
        self.argv: tuple[str, ...] = ()
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, *argv: str, **kwargs: Any) -> FakeProc:
        self.argv, self.kwargs = argv, kwargs
        if isinstance(self.proc, Exception):
            raise self.proc
        return self.proc


def test_node_runner_builds_exact_docker_argv_and_parses_reply() -> None:
    reply = {
        "stdout": "hi\n",
        "result": {"a": 1},
        "figures": [],
        "error": None,
        "ms": 12.5,
    }
    proc = FakeProc(out=b"pyodide loading...\n" + json.dumps(reply).encode() + b"\n")
    spawn = Spawner(proc)
    runner = NodeRunner(repo_root=Path("/repo"), spawn=spawn)
    body = asyncio.run(runner.run("print(1)", 10))
    assert spawn.argv == (
        "docker",
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--env-file",
        "/dev/null",
        "-v",
        "/repo/runner:/runner:ro",
        "node:22-slim",
        "node",
        "/runner/node-pyodide.mjs",
    )
    assert body == ResultBody(stdout="hi\n", result={"a": 1}, ms=12.5)
    assert proc.stdin_data is not None
    assert json.loads(proc.stdin_data) == {"code": "print(1)", "timeout_s": 10}
    assert proc.stdin_data.endswith(b"\n") and proc.stdin_data.count(b"\n") == 1
    assert spawn.kwargs.get("stdin") is not None  # piped, never a shell


def test_node_runner_image_and_command_are_configurable() -> None:
    spawn = Spawner(FakeProc(out=b'{"ms": 1}\n'))
    runner = NodeRunner(
        repo_root=Path("/r"),
        image="my/img:1",
        command=("node", "/runner/x.mjs"),
        spawn=spawn,
    )
    asyncio.run(runner.run("1", 5))
    assert spawn.argv[-3:] == ("my/img:1", "node", "/runner/x.mjs")


def test_node_runner_timeout_kills_and_reports() -> None:
    proc = FakeProc(hang=True)
    runner = NodeRunner(repo_root=Path("/r"), spawn=Spawner(proc), grace_s=0.0)
    body = asyncio.run(runner.run("while True: pass", 0.01))
    assert body == ResultBody(error="timeout", ms=0)
    assert proc.killed


def test_node_runner_default_grace_is_20_seconds() -> None:
    assert NodeRunner(repo_root=Path("/r")).grace_s == 20.0


def test_node_runner_missing_docker() -> None:
    runner = NodeRunner(
        repo_root=Path("/r"), spawn=Spawner(FileNotFoundError("docker"))
    )
    with pytest.raises(RunnerUnavailable, match="docker"):
        asyncio.run(runner.run("1", 10))


def test_node_runner_bad_output_is_an_error_body() -> None:
    runner = NodeRunner(
        repo_root=Path("/r"), spawn=Spawner(FakeProc(out=b"", err=b"boom\n", code=1))
    )
    body = asyncio.run(runner.run("1", 10))
    assert body.error is not None and "boom" in body.error
    runner = NodeRunner(
        repo_root=Path("/r"), spawn=Spawner(FakeProc(out=b"not json\n"))
    )
    body = asyncio.run(runner.run("1", 10))
    assert body.error is not None and "runner" in body.error


# ---- problems ----

P1 = {
    "id": "P1-01",
    "question": "A first-order reaction ... how long to 90% conversion, in minutes?",
    "answer": {"value": 51.1686, "unit": "min"},
    "tolerance_rel": 0.01,
    "method_1": "t = ln(1/(1-X))/k",
    "method_2": "solve_ivp",
    "topic": "CRE: batch reactor, first order",
    "difficulty": "easy",
    "source_note": "standard textbook form; numbers original",
}
P2 = {
    "id": "P1-02",
    "question": "A 0.50 m^3 tank holds nitrogen ... how many moles?",
    "answer": {"value": 72.1634, "unit": "mol"},
    "method_1": "n = PV/(RT)",
    "topic": "Thermodynamics: ideal gas",
}


def test_load_problems_accepts_list_and_wrapped(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    a.write_text(json.dumps([P1, P2]))
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"problems": [P1, P2]}))
    for path in (a, b):
        ps = load_problems(path)
        assert [p.id for p in ps] == ["P1-01", "P1-02"]
        assert ps[0].answer.value == 51.1686 and ps[0].answer.unit == "min"
        assert ps[0].tolerance_rel == 0.01
        assert ps[0].difficulty == "easy"
        assert ps[1].tolerance_rel == 0.01  # default
        assert ps[1].difficulty is None


def test_load_problems_rejects_other_shapes(tmp_path: Path) -> None:
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"nope": []}))
    with pytest.raises(TypeError):
        load_problems(f)
