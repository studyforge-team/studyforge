"""Agent loop and browser tool bridge (ticket S2, master plan §3.5-3.6).

DB-free core: start() and on_result() read and write SolveState through deps.store,
so the route layer, the eval runner (T4) and tests drive the same code.

Calc path: classify (router) -> notes search once (not a counted step) ->
ChemLab template if one fits (CH3: server-built code, one run, no second method) ->
otherwise next_action (solver, native tool calls; a fenced ```python block is the fallback) ->
the browser runs run_python -> deterministic verify -> explain (JSON, reasoning off)
-> number guardrail -> final. Limits: 4 counted tool steps and 90 s of server wall
clock from the first next_action. Every failure ends as a final step with
confidence "low", never an HTTP error (the web client does not read error bodies).
"""

import json
import re
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from app.agent import guardrail, prompts
from app.agent.chemlab_pick import pick_template
from app.agent.state import SolveNotFound, SolveState, StateStore
from app.agent.steps import (
    Final,
    NeedConfirm,
    ResultBody,
    RunPython,
    Source,
    Step,
    step_json,
)
from app.agent.tools import (
    TOOL_SCHEMAS,
    StubTools,
    ToolImpls,
    ToolRefused,
    check_mermaid,
    hits_as_data,
    parse_args,
)
from app.agent.verify import clean, flat_numbers, verify
from app.llm.client import LLMResult, Message
from app.llm.errors import LLMError

MAX_STEPS = 4
BUDGET_S = 90.0
MAX_VERIFY_FAILURES = 2
MODEL_STDOUT_CHARS = 2000  # what the model sees of stdout
_FENCED = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL)


class Model(Protocol):
    """The parts of app.llm.LLMClient the loop uses."""

    async def chat(
        self, role: str, messages: list[Message], *, deadline: float | None = ...,
        solve_id: str | None = ..., reasoning: bool | None = ...,
    ) -> LLMResult: ...  # fmt: skip

    async def chat_tools(
        self, role: str, messages: list[Message], tools: list[dict[str, Any]], *,
        deadline: float | None = ..., solve_id: str | None = ..., tool_choice: str = ...,
    ) -> LLMResult: ...  # fmt: skip

    async def chat_json[T: BaseModel](
        self, role: str, messages: list[Message], schema: type[T], *,
        deadline: float | None = ..., solve_id: str | None = ...,
    ) -> tuple[T, LLMResult]: ...  # fmt: skip


# guard(answer_md, result, question) -> numbers written in the answer that are not
# supported (B8). None skips the check.
Guard = Callable[[str, Any, str], Sequence[str]]


def b8_guard(answer_md: str, result: Any, question: str) -> list[str]:
    """B8: every number must come from the sandbox result or the question."""
    allowed = guardrail.allowed_numbers(result, question)
    return [f.text for f in guardrail.check(answer_md, allowed).unsupported]


@dataclass
class Deps:
    llm: Model
    store: StateStore
    clock: Callable[[], float]
    tools: ToolImpls = field(default_factory=StubTools)
    guard: Guard | None = b8_guard
    read_upload: Callable[[str], Awaitable[str]] | None = None  # C2 text
    # ChemLab SPECs as data ({template: SPEC}); None turns template picking off
    templates: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None
    regenerate_on_flag: bool = True  # cut-line step 1 sets False: flag only


class Kind(BaseModel):
    kind: Literal["calc", "concept"]


class Explanation(BaseModel):
    answer_md: str


async def start(
    question: str,
    deps: Deps,
    *,
    user_id: str,
    upload_id: str | None = None,
    confirmed: bool = False,
) -> tuple[str, dict[str, Any]]:
    """POST /solve. Returns (solve_id, step). After the student confirms the text read
    from an upload, the client posts again with confirmed=True and the edited text."""
    state = SolveState(
        id=uuid.uuid4().hex, user_id=user_id, question=question, upload_id=upload_id
    )
    if upload_id and not confirmed and deps.read_upload is not None:
        text = await deps.read_upload(upload_id)
        state.status = "awaiting_confirm"
        return state.id, await _issue(state, NeedConfirm(extracted_text=text), deps)
    try:
        step = await _begin(state, deps)
    except LLMError as err:
        step = _failed(state, err)
    return state.id, await _issue(state, step, deps)


async def on_result(
    solve_id: str, user_id: str, body: ResultBody, deps: Deps
) -> dict[str, Any]:
    """POST /solve/{id}/result. Posts for one solve are serialised by the store lock.
    A result posted when no run is pending gets the stored step back. Identical
    bodies are NOT de-duplicated: the same failing code posts identical bodies on
    every run, and the result body carries no step number to tell a network retry
    from a new run (contract request). A result for another user's solve is not
    found."""
    async with deps.store.lock(solve_id):
        state = await deps.store.get(solve_id)
        if state is None or state.user_id != user_id:
            raise SolveNotFound(solve_id)
        if state.status != "awaiting_result":
            assert state.last_step is not None
            return state.last_step
        try:
            step = await _after_run(state, body, deps)
        except LLMError as err:
            step = _failed(state, err)
        return await _issue(state, step, deps)


async def get_step(solve_id: str, user_id: str, deps: Deps) -> dict[str, Any]:
    """GET /solve/{id}: the pending step, to resume after a restart (contract request)."""
    state = await deps.store.get(solve_id)
    if state is None or state.user_id != user_id or state.last_step is None:
        raise SolveNotFound(solve_id)
    return state.last_step


async def _issue(state: SolveState, step: Step, deps: Deps) -> dict[str, Any]:
    wire = step_json(step)
    state.last_step = wire
    if isinstance(step, Final):
        state.status = "done"
    elif isinstance(step, RunPython):
        state.status = "awaiting_result"
    await deps.store.save(state)
    return wire


def _spend(state: SolveState, res: LLMResult) -> LLMResult:
    state.cost_usd += res.cost_usd
    return res


async def _begin(state: SolveState, deps: Deps) -> Step:
    q = _quoted(state.question)
    kind, res = await deps.llm.chat_json(
        "router",
        [
            {"role": "system", "content": prompts.CLASSIFY},
            {"role": "user", "content": q},
        ],
        Kind,
        solve_id=state.id,
    )
    _spend(state, res)
    state.kind = kind.kind
    hits = await deps.tools.search_my_notes(state.user_id, state.question)
    state.sources = [{"title": h.title, "url": h.url} for h in hits]
    notes = f"\n\nStudent's notes (quoted data):\n{hits_as_data(hits)}" if hits else ""
    if kind.kind == "concept":
        res = await deps.llm.chat(
            "solver",
            [
                {"role": "system", "content": prompts.CONCEPT + notes},
                {"role": "user", "content": q},
            ],
            solve_id=state.id,
        )
        _spend(state, res)
        return _final(state, res.text, "medium")
    state.messages = [
        {"role": "system", "content": prompts.SOLVER + notes},
        {"role": "user", "content": q},
    ]
    if deps.templates:
        state.started_at = deps.clock()
        run, cost = await pick_template(
            deps.llm,
            state.question,
            deps.templates,
            deadline=state.started_at + BUDGET_S,
            solve_id=state.id,
        )
        state.cost_usd += cost
        if run is not None:
            state.template = run.template
            state.steps_used += 1
            state.pending_call_id = None
            return RunPython(code=run.code)
    return await _next_action(state, deps)


async def _next_action(state: SolveState, deps: Deps, role: str = "solver") -> Step:
    while True:
        if state.started_at is None:
            state.started_at = deps.clock()
        deadline = state.started_at + BUDGET_S
        if state.steps_used >= MAX_STEPS or deps.clock() >= deadline:
            return await _out_of_budget(state, deps)
        res = _spend(
            state,
            await deps.llm.chat_tools(
                role, state.messages, TOOL_SCHEMAS, deadline=deadline, solve_id=state.id
            ),
        )
        state.steps_used += 1
        if not res.tool_calls:
            fenced = _FENCED.search(res.text)
            state.messages.append({"role": "assistant", "content": res.text})
            if fenced:  # fallback when native tool calling is not used
                state.pending_call_id = None
                return RunPython(code=fenced.group(1).strip())
            state.messages.append(
                {
                    "role": "user",
                    "content": "Compute it: call run_python with the code.",
                }
            )
            continue
        call = res.tool_calls[0]  # one tool per turn keeps the step count honest
        state.messages.append(
            {
                "role": "assistant",
                "content": res.text or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                ],
            }
        )
        try:
            args = parse_args(call.name, call.arguments)
            if call.name == "run_python":
                code = str(args["code"]).strip()
                if not code:
                    raise ToolRefused("run_python: code is empty")
                state.pending_call_id = call.id
                return RunPython(code=code)
            reply = await _run_server_tool(state, call.name, args, deps)
        except ToolRefused as err:
            reply = f"refused: {err}"
        state.messages.append(
            {"role": "tool", "tool_call_id": call.id, "content": reply}
        )


async def _run_server_tool(
    state: SolveState, name: str, args: dict[str, Any], deps: Deps
) -> str:
    if name == "draw_diagram":
        state.diagram = check_mermaid(str(args["mermaid"]))
        return "diagram attached to the answer"
    if name in ("search_my_notes", "web_search"):
        query = str(args["query"])
        hits = (
            await deps.tools.search_my_notes(state.user_id, query)
            if name == "search_my_notes"
            else await deps.tools.web_search(query)
        )
        state.sources += [{"title": h.title, "url": h.url} for h in hits]
        return f"results (quoted data): {hits_as_data(hits)}"
    if name == "make_quiz":
        return await deps.tools.make_quiz(
            state.user_id, str(args["topic"]), int(args["n_items"])
        )
    return await deps.tools.schedule_reminder(
        state.user_id, str(args["title"]), str(args["due_at_utc"])
    )


async def _after_run(state: SolveState, body: ResultBody, deps: Deps) -> Step:
    run = clean(body)
    state.figures = (state.figures + run.figures)[:4]
    report = {
        "stdout": run.stdout[-MODEL_STDOUT_CHARS:],
        "result": run.result,
        "error": run.error,
    }
    _tell(state, json.dumps(report, ensure_ascii=False))
    if state.template is not None:
        template, state.template = state.template, None
        result = None if run.error else _template_result(run.result)
        if result is not None:
            state.result = result
            return await _explain(state, deps)
        errors = run.error or json.dumps(
            run.result.get("errors") if isinstance(run.result, dict) else run.result
        )
        state.messages.append(
            {
                "role": "user",
                "content": f"The ChemLab {template} template could not answer this "
                f"({errors}). Solve it with run_python instead.",
            }
        )
        return await _next_action(state, deps)
    if run.error:
        return await _next_action(state, deps, _role(state))
    verdict = verify(run.result)
    if verdict.ok:
        if state.cross_check == "pending":
            return await _settle_cross_check(state, run.result, deps)
        state.result = run.result
        return await _explain(state, deps)
    state.verify_failures += 1
    if state.cross_check == "pending":  # the cross-check itself failed verify
        state.cross_check = "disagreed"
        state.flags.append("cross_check_failed")
        return await _out_of_budget(state, deps)
    if verdict.disagree or state.verify_failures >= MAX_VERIFY_FAILURES:
        state.cross_check = "pending"
        answer = run.result.get("answer") if isinstance(run.result, dict) else None
        if isinstance(answer, dict) and isinstance(answer.get("value"), int | float):
            state.first_answer = float(answer["value"])
        state.messages.append({"role": "user", "content": prompts.CROSS_CHECK})
        return await _next_action(state, deps, "cross_check")
    state.messages.append(
        {
            "role": "user",
            "content": prompts.REPAIR.format(reason=verdict.reason),
        }
    )
    return await _next_action(state, deps)


async def _settle_cross_check(state: SolveState, result: Any, deps: Deps) -> Step:
    new = float(result["answer"]["value"])
    old = state.first_answer
    # no earlier valid answer to compare with: the cross-check's own two methods agreed
    agree = old is None or abs(new - old) <= 1e-3 * max(abs(new), abs(old), 1e-12)
    state.cross_check = "agreed" if agree else "disagreed"
    if not agree:
        state.flags.append("cross_check_disagreed")
    state.result = result
    return await _explain(state, deps)


async def _explain(state: SolveState, deps: Deps) -> Step:
    deadline = (state.started_at or deps.clock()) + BUDGET_S
    data = json.dumps(state.result, ensure_ascii=False)
    messages: list[Message] = [
        {"role": "system", "content": prompts.EXPLAIN},
        {
            "role": "user",
            "content": f"{_quoted(state.question)}\n\nSandbox result:\n{data}",
        },
    ]
    exp, res = await deps.llm.chat_json(
        "solver", messages, Explanation, deadline=deadline, solve_id=state.id
    )
    _spend(state, res)
    answer = exp.answer_md
    bad = list(deps.guard(answer, state.result, state.question)) if deps.guard else []
    if bad and deps.regenerate_on_flag and deps.clock() < deadline:
        messages += [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": prompts.REGENERATE.format(bad=", ".join(bad))},
        ]
        exp, res = await deps.llm.chat_json(
            "solver", messages, Explanation, deadline=deadline, solve_id=state.id
        )
        _spend(state, res)
        answer = exp.answer_md
        bad = (
            list(deps.guard(answer, state.result, state.question)) if deps.guard else []
        )
    if bad:
        state.flags.append("unsupported_numbers")
    if state.flags:
        confidence: Literal["high", "medium", "low"] = "low"
    elif state.cross_check == "agreed":
        confidence = "medium"
    else:
        confidence = "high"
    return _final(state, answer, confidence)


async def _out_of_budget(state: SolveState, deps: Deps) -> Step:
    """Honest partial answer: no numbers that were not verified."""
    state.flags.append("limit_reached")
    text = (
        "I couldn't finish a verified answer within the limits for one solve "
        "(4 tool steps, 90 seconds), so I'm not giving a number I can't stand behind. "
        "Try rephrasing the question, or split it into smaller parts."
    )
    return _final(state, text, "low", with_numbers=False)


def _failed(state: SolveState, err: LLMError) -> Step:
    state.flags.append(type(err).__name__)
    return _final(
        state,
        "The model is not available right now, so I can't solve this yet. "
        "Please try again in a minute.",
        "low",
        with_numbers=False,
    )


def _final(
    state: SolveState,
    answer_md: str,
    confidence: Literal["high", "medium", "low"],
    with_numbers: bool = True,
) -> Final:
    numbers = (
        flat_numbers(state.result)
        if with_numbers and isinstance(state.result, dict)
        else {}
    )
    return Final(
        answer_md=answer_md,
        numbers=numbers,
        figures=state.figures if with_numbers else [],
        diagram_mermaid=state.diagram,
        sources=[Source(**s) for s in state.sources],
        confidence=confidence,
    )


_STEADY_UNITS = {"T": "K", "X": "-", "CA": "mol/m^3", "Da": "-"}


def _template_result(result: Any) -> dict[str, Any] | None:
    """A ChemLab template's output in the loop's result shape, or None if it failed.
    Steady states are flattened into named values so the guardrail allows them."""
    if not isinstance(result, dict) or result.get("ok") is not True:
        return None
    outputs = result.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        return None
    values = dict(outputs)
    states = result.get("steady_states") or []
    if len(states) > 1:
        for i, st in enumerate(states, 1):
            for key, unit in _STEADY_UNITS.items():
                if isinstance(st, dict) and isinstance(st.get(key), int | float):
                    values[f"steady_state_{i}_{key}"] = {"value": st[key], "unit": unit}
    return {
        "template": result.get("template"),
        "inputs": result.get("inputs", {}),
        "values": values,
        "steady_states": states,  # keeps the stable/unstable flags for the explanation
        "warnings": result.get("warnings", []),
    }


def _tell(state: SolveState, content: str) -> None:
    """Report a sandbox run back to the model in the form it asked for it."""
    if state.pending_call_id:
        state.messages.append(
            {"role": "tool", "tool_call_id": state.pending_call_id, "content": content}
        )
        state.pending_call_id = None
    else:
        state.messages.append(
            {"role": "user", "content": f"Sandbox output:\n{content}"}
        )


def _role(state: SolveState) -> str:
    return "cross_check" if state.cross_check == "pending" else "solver"


def _quoted(question: str) -> str:
    return f'Question (quoted data):\n"""\n{question}\n"""'
