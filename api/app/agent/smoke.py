"""Smoke/eval harness (tickets S2b and TD1): drive the agent loop in-process over a
set of problems and score the answers.

Rule 1: neither the server nor this harness executes model-written code. A run_python
step goes to a Runner: in real runs the CI Node runner (runner/node-pyodide.mjs) inside
`docker --network none` with an empty environment; in tests a fake.
"""

import asyncio
import json
import statistics
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError

from app.agent import loop
from app.agent.loop import Deps
from app.agent.steps import ResultBody

SMOKE_USER = "smoke"
DEFAULT_IMAGE = "node:22-slim"
DEFAULT_COMMAND = ("node", "/runner/node-pyodide.mjs")
TIMEOUT_GRACE_S = 20.0
REPO_ROOT = Path(__file__).resolve().parents[3]


class RunnerUnavailable(RuntimeError):
    """The sandbox runner cannot be started (for example docker is not installed)."""


class Runner(Protocol):
    async def run(self, code: str, timeout_s: float) -> ResultBody:
        """Execute a run_python step and return what the browser worker would post."""
        ...


class _Proc(Protocol):
    @property
    def returncode(self) -> int | None: ...
    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]: ...
    def kill(self) -> None: ...
    async def wait(self) -> int: ...


Spawn = Callable[..., Awaitable[_Proc]]


async def _spawn_exec(*argv: str, **kwargs: Any) -> _Proc:
    return await asyncio.create_subprocess_exec(*argv, **kwargs)


class NodeRunner:
    """Runs code in the Node Pyodide runner under docker: no network, empty
    environment, runner directory mounted read-only. One container per run; the
    request is one JSON line on stdin, the reply one JSON line on stdout."""

    def __init__(
        self,
        *,
        repo_root: Path = REPO_ROOT,
        image: str = DEFAULT_IMAGE,
        command: Sequence[str] = DEFAULT_COMMAND,
        docker: str = "docker",
        grace_s: float = TIMEOUT_GRACE_S,
        spawn: Spawn = _spawn_exec,
    ) -> None:
        self.repo_root = repo_root
        self.image = image
        self.command = tuple(command)
        self.docker = docker
        self.grace_s = grace_s
        self._spawn = spawn

    def argv(self) -> tuple[str, ...]:
        return (
            self.docker, "run", "--rm", "-i",
            "--network", "none",
            "--env-file", "/dev/null",
            "-v", f"{self.repo_root / 'runner'}:/runner:ro",
            self.image, *self.command,
        )  # fmt: skip

    async def run(self, code: str, timeout_s: float) -> ResultBody:
        try:
            proc = await self._spawn(
                *self.argv(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as err:
            raise RunnerUnavailable(
                f"cannot start the sandbox runner: '{self.docker}' was not found. "
                "Install docker (the runner must run in `docker --network none`); "
                "model-written code is never run outside it."
            ) from err
        request = json.dumps({"code": code, "timeout_s": timeout_s}) + "\n"
        try:
            out, errs = await asyncio.wait_for(
                proc.communicate(request.encode()), timeout_s + self.grace_s
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return ResultBody(error="timeout", ms=0)
        return _parse_reply(out, errs, proc.returncode)


def _parse_reply(out: bytes, err: bytes, returncode: int | None) -> ResultBody:
    lines = [ln for ln in out.decode("utf-8", "replace").splitlines() if ln.strip()]
    if lines:
        try:
            return ResultBody.model_validate(json.loads(lines[-1]))
        except (ValueError, ValidationError):
            pass
    tail = err.decode("utf-8", "replace").strip()[-500:]
    return ResultBody(
        error=f"runner failed (exit {returncode}) without a valid reply: {tail}"
        if tail or not lines
        else "runner reply was not valid JSON",
        ms=0,
    )


# ---- problems and scoring ----


class Answer(BaseModel):
    value: float
    unit: str


class Problem(BaseModel):
    """One golden-style problem; extra fields in the file are ignored."""

    id: str
    question: str
    answer: Answer
    tolerance_rel: float = 0.01
    topic: str | None = None
    difficulty: str | None = None


def load_problems(path: Path) -> list[Problem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("problems")
    if not isinstance(data, list):
        raise TypeError(f"{path}: expected a list or an object with 'problems'")
    return [Problem.model_validate(item) for item in data]


def _unit(text: str) -> str:
    return text.replace(" ", "").replace("**", "^")


def _answer_key(numbers: dict[str, float]) -> str | None:
    if "answer" in numbers:
        return "answer"
    return next((k for k in numbers if k.startswith("answer (")), None)


def score(
    problem: Problem, final: dict[str, Any]
) -> tuple[bool, float | None, str | None]:
    """(correct, number found, key it was found under). A unit in the key that differs
    from the expected unit is wrong; a bare "answer" key carries no unit to compare."""
    numbers: dict[str, float] = final.get("numbers") or {}
    key = _answer_key(numbers)
    if key is None:
        return False, None, None
    got = float(numbers[key])
    unit = key.removeprefix("answer (").removesuffix(")")
    if key != "answer" and _unit(unit) != _unit(problem.answer.unit):
        return False, got, key
    want = problem.answer.value
    return abs(got - want) <= problem.tolerance_rel * abs(want), got, key


# ---- solving ----

Status = Literal["correct", "wrong", "abstained", "error"]


@dataclass
class Outcome:
    final: dict[str, Any] | None
    seconds: float
    runs: int
    cost_usd: float
    confidence: str | None
    error: str | None = None


async def solve_one(
    problem: Problem, deps: Deps, runner: Runner, *, max_runs: int = 8
) -> Outcome:
    t0 = deps.clock()
    solve_id, step = await loop.start(problem.question, deps, user_id=SMOKE_USER)
    runs = 0
    error: str | None = None
    final: dict[str, Any] | None = None
    while True:
        kind = step.get("type")
        if kind == "final":
            final = step
            break
        if kind != "run_python":
            error = str(kind)  # need_confirm: a smoke run has nobody to confirm
            break
        if runs >= max_runs:
            error = "max_runs"
            break
        runs += 1
        body = await runner.run(step["code"], step.get("timeout_s", 10))
        step = await loop.on_result(solve_id, SMOKE_USER, body, deps)
    state = await deps.store.get(solve_id)
    return Outcome(
        final=final,
        seconds=deps.clock() - t0,
        runs=runs,
        cost_usd=state.cost_usd if state else 0.0,
        confidence=final["confidence"] if final else None,
        error=error,
    )


# ---- suite and report ----


@dataclass
class Row:
    id: str
    status: Status
    expected: float
    unit: str
    got: float | None
    key: str | None
    seconds: float
    runs: int
    cost_usd: float
    confidence: str | None
    note: str = ""


def _row(problem: Problem, out: Outcome) -> Row:
    base: dict[str, Any] = {
        "id": problem.id,
        "expected": problem.answer.value,
        "unit": problem.answer.unit,
        "seconds": out.seconds,
        "runs": out.runs,
        "cost_usd": out.cost_usd,
        "confidence": out.confidence,
    }
    if out.final is None:
        return Row(status="error", got=None, key=None, note=out.error or "", **base)
    correct, got, key = score(problem, out.final)
    if correct:
        return Row(status="correct", got=got, key=key, **base)
    if out.final.get("confidence") == "low" and not out.final.get("numbers"):
        return Row(status="abstained", got=None, key=None, **base)
    note = "" if key else "no answer key"
    return Row(status="wrong", got=got, key=key, note=note, **base)


@dataclass
class Report:
    rows: list[Row]

    @property
    def total(self) -> int:
        return len(self.rows)

    def _count(self, status: Status) -> int:
        return sum(1 for r in self.rows if r.status == status)

    @property
    def correct(self) -> int:
        return self._count("correct")

    @property
    def abstained(self) -> int:
        return self._count("abstained")

    @property
    def errors(self) -> int:
        return self._count("error")

    @property
    def wrong_numbers(self) -> int:
        return sum(1 for r in self.rows if r.status == "wrong" and r.got is not None)

    @property
    def median_seconds(self) -> float:
        return statistics.median(r.seconds for r in self.rows) if self.rows else 0.0

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.rows)

    def passed(
        self, threshold: float = 0.8, *, max_median_s: float | None = None
    ) -> bool:
        """S2b: correct/total >= threshold (8/10). S2: median <= 60 s."""
        if not self.total or self.correct / self.total < threshold:
            return False
        return max_median_s is None or self.median_seconds <= max_median_s

    def to_markdown(self) -> str:
        head = [
            f"**Correct: {self.correct}/{self.total}** "
            f"({self.correct / self.total:.0%})"
            if self.total
            else "**No problems**",
            "",
            f"- abstained: {self.abstained}",
            f"- wrong numbers: {self.wrong_numbers}",
            f"- errors: {self.errors}",
            f"- median seconds: {self.median_seconds:.1f}",
            f"- model cost: ${self.total_cost:.4f}",
            "",
            "| id | status | expected | got | seconds | runs | cost | confidence | note |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in self.rows:
            got = "" if r.got is None else f"{r.got:g}"
            note = f"{r.key or ''} {r.note}".strip().replace("|", "/")
            head.append(
                f"| {r.id} | {r.status} | {r.expected:g} {r.unit} | {got} | "
                f"{r.seconds:.1f} | {r.runs} | ${r.cost_usd:.4f} | "
                f"{r.confidence or ''} | {note} |"
            )
        return "\n".join(head) + "\n"


async def run_suite(
    problems: Sequence[Problem], deps_factory: Callable[[], Deps], runner: Runner
) -> Report:
    """Sequential; a fresh Deps (store, clock) per problem."""
    rows = []
    for problem in problems:
        out = await solve_one(problem, deps_factory(), runner)
        rows.append(_row(problem, out))
    return Report(rows)
