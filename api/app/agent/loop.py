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
from app.agent.chemlab_pick import drop_sizing_outputs, pick_template, required_inputs
from app.agent.markup import tidy_markdown
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
from app.agent.verify import (
    AGREE_REL,
    clean,
    energy_sign_problem,
    flat_numbers,
    verify,
)
from app.llm.client import LLMResult, Message
from app.llm.errors import BudgetExceeded, LLMError

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
    allowed += [
        f.value for a in _assumptions(result) for f in guardrail.parse_numbers(a)
    ]
    allowed += guardrail.percents(question)
    return [
        f.text for f in guardrail.check(answer_md, allowed, _quantities(result)).unsupported
    ]


def _quantities(result: Any) -> list[tuple[float, str]]:
    if not isinstance(result, dict):
        return []
    nodes = [result.get("answer"), result.get("check"), *(result.get("values") or {}).values()]
    return [
        (float(n["value"]), n["unit"])
        for n in nodes
        if isinstance(n, dict)
        and isinstance(n.get("value"), int | float)
        and not isinstance(n["value"], bool)
        and isinstance(n.get("unit"), str)
    ]


def _assumptions(result: Any) -> list[str]:
    items = result.get("assumptions") if isinstance(result, dict) else None
    return [a for a in items if isinstance(a, str)] if isinstance(items, list) else []


def _invented(result: Any, question: str) -> bool:
    """A: an assumption states a number that is not in the question, not a known
    constant and not a small integer."""
    given = [f.value for f in guardrail.parse_numbers(question)]
    return any(guardrail.check(a, given).unsupported for a in _assumptions(result))


def _unsupplied(
    spec: Mapping[str, Mapping[str, Any]], given: Mapping[str, float]
) -> list[str]:
    """H: spec inputs the pick left to their defaults. Off switches (default 0) and
    inputs a supplied one overrides ("k ... overrides k0, Ea, T") do not count."""
    skip = {
        w
        for g in given
        for w in re.findall(
            r"\w+",
            str(spec.get(g, {}).get("description", "")).partition("overrides")[2],
        )
    }
    return [
        n
        for n, s in spec.items()
        if n not in given and n not in skip and s.get("default") != 0
    ]


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


OFF_TOPIC_REPLY = (
    "I can only help with engineering, science and maths coursework — "
    "calculations, concepts, and your notes. That question is outside what I do, "
    "so I won't guess at it. Try asking about a topic from your course."
)


class Kind(BaseModel):
    # fail open: a reply missing study/live answers the question rather than erroring
    study: bool = True
    live: bool = False
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
        step = (
            await _capped(state, deps)
            if isinstance(err, BudgetExceeded)
            else _failed(state, err)
        )
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
            step = (
                await _capped(state, deps)
                if isinstance(err, BudgetExceeded)
                else _failed(state, err)
            )
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


_INJECTION = re.compile(
    r"\b(?:ignore|disregard|forget)\b(?:\W+\w+){0,3}?\W+(?:all|any|your|the|previous|prior|above)\b"
    r"(?:\W+\w+){0,3}?\W+(?:rules|instructions|prompt|guidelines)\b"
    r"|system prompt|jailbreak",  # not "you are now": physics problems say "you are now standing..."
    re.IGNORECASE,
)
_DAN = re.compile(r"\bDAN\b")  # caps only: "Dan" is a name
# build verb + general-software artifact within a few words; the router sometimes calls these study=true
_SOFTWARE = re.compile(
    r"\b(?:write|build|make|create|code|develop|program|generate)\b(?:\W+\w+){0,4}?\W+"
    r"(?:web\s*scraper|scraper|crawler(?!\s+(?:crane|excavator|tractor|dozer))|website|web\s*app"
    r"|landing\s+page|chrome\s+extension|browser\s+extension|discord\s+bot|telegram\s+bot"
    r"|whatsapp\s+bot|chatbot|bot|mobile\s+app|android\s+app|ios\s+app|login\s+page"
    r"|e-commerce|online\s+store)\b(?!-)",  # crawler crane is equipment; "website-style" is not a website
    re.IGNORECASE,
)
# live/current facts (sports results, news, prices, weather): phrase-level so "score", "price elasticity", "current density" pass
_LIVE = re.compile(
    r"\bwho\s+(?:won|wins)\b(?:\W+\w+){0,5}?\W+(?:match|game|final|league|cup|series|tournament|ipl|last\s+night|yesterday|today)\b"
    r"|\b(?:match|cricket|football|live)\s+(?:score|result)s?\b|\bfinal\s+scores?\b|\bipl\b|\bworld\s+cup\b|\b(?:premier|champions)\s+league\b"
    r"|\b(?:nba|nfl)\b|\b(?:match|game|final)\b[^.?]{0,30}\blast\s+night\b|\blast\s+night\b[^.?]{0,30}\b(?:match|game|final)\b"
    r"|\b(?:latest|breaking)\s+news\b|\belection\s+results?\b"
    r"|\b(?:stock|share)\s+price\b|\b(?:current|currently|latest|live|today|now)\s+price\s+of\s+(?:bitcoin|crypto\w*|gold|petrol|diesel)\b(?!\s*(?:is|=|:|at|of)?\s*(?:rs\.?|inr|usd)?\s*[₹$]?\s*\d)"
    r"|\bprice\s+of\s+(?:bitcoin|crypto\w*|gold|petrol|diesel)\b[^.?!;,\d₹$]{0,25}\b(?:today|now|currently)\b"
    r"|\bprice\b[^.?]{0,20}\bright\s+now\b|\bright\s+now\b[^.?]{0,20}\bprice\b|\btoday'?s\s+price\b"
    r"|\bexchange\s+rate\s+today\b|\bweather\s+(?:today|tomorrow|forecast)\b|\b(?:today|tomorrow)'?s\s+weather\b",
    re.IGNORECASE,
)


async def _begin(state: SolveState, deps: Deps) -> Step:
    q0 = state.question
    if _INJECTION.search(q0) or _DAN.search(q0) or _SOFTWARE.search(q0) or _LIVE.search(q0):
        state.kind = "off_topic"  # no router call: the router can be talked into study=True
        return _final(state, OFF_TOPIC_REPLY, "medium", with_numbers=False)
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
    off_topic = (
        not kind.study or kind.live
    )  # code decides; the model only answers facts
    state.kind = "off_topic" if off_topic else kind.kind
    if off_topic:  # fixed refusal: no notes search, no 2nd LLM call
        return _final(state, OFF_TOPIC_REPLY, "medium", with_numbers=False)
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
            spec = deps.templates[run.template]
            need = required_inputs(run.template, spec, state.question)
            if need is not None:  # sizing-only inputs may stay default when sizing isn't asked
                spec = {k: v for k, v in spec.items() if k in need}
            if _unsupplied(spec, run.values):
                run = None  # defaults would be invented inputs: use the normal solver
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
    if state.template is not None and isinstance(run.result, dict):
        _strip_sizing(state.template, run.result, state.question)
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
    answer = run.result.get("answer") if isinstance(run.result, dict) else None
    value = answer.get("value") if isinstance(answer, dict) else None
    if state.cross_check == "pending":  # the cross-check itself failed verify
        old = state.first_answer
        if (
            isinstance(value, int | float)
            and old is not None
            and abs(value - old) <= AGREE_REL * max(abs(value), abs(old))
        ):  # its answer is the first answer: only its own check is bad
            return await _settle_cross_check(state, run.result, deps)
        state.cross_check = "disagreed"
        state.flags.append("cross_check_failed")
        return _final(state, _CROSS_CHECK_FAILED, "low", with_numbers=False)
    if verdict.disagree or state.verify_failures >= MAX_VERIFY_FAILURES:
        if isinstance(value, int | float):
            state.first_answer = float(value)
        if verdict.disagree and _SOFT_FLAG not in state.flags:
            state.flags.append(_SOFT_FLAG)  # medium at best from here on
            state.messages.append({"role": "user", "content": prompts.DISAGREE})
            return await _next_action(state, deps)
        state.cross_check = "pending"
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
    agree = old is None or abs(new - old) <= AGREE_REL * max(abs(new), abs(old))
    state.cross_check = "agreed" if agree else "disagreed"
    if not agree:
        state.flags.append("cross_check_disagreed")
    elif old is not None:  # state the agreement that really happened
        result = {
            **result,
            "check": {
                "value": old,
                "unit": result["answer"]["unit"],
                "method": "independent re-solve (first attempt)",
            },
        }
    state.result = result
    return await _explain(state, deps)


_PLACEHOLDER = re.compile(r"<(?!(?:br|sub|sup)>)[a-z]+(?:_[a-z]+)*>|\{<[^{}]*>\}|\${3,}")


def _has_placeholder(md: str) -> bool:
    """Unfilled template text such as <number>, {<value>} or a run of $$$."""
    return _PLACEHOLDER.search(md) is not None


def _shows_answer(md: str, result: Any) -> bool:
    node = result.get("answer") if isinstance(result, dict) else None
    value = node.get("value") if isinstance(node, dict) else None
    if not isinstance(value, int | float) or isinstance(value, bool):
        return True
    return f"{value:g}" in md.replace(",", "").replace("{,}", "")


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
        retry = exp.answer_md
        if not _has_placeholder(retry) and (
            _shows_answer(retry, state.result) or not _shows_answer(answer, state.result)
        ):
            answer = retry
            bad = (
                list(deps.guard(answer, state.result, state.question))
                if deps.guard
                else []
            )
    if _has_placeholder(answer):
        state.flags.append("placeholder_text")
    if bad:
        state.flags.append("unsupported_numbers: " + ", ".join(bad))
    if isinstance(state.result, dict):  # the write-up may skip the solver's assumptions: show them
        given = state.result.get("assumptions")
        if (
            isinstance(given, list)
            and given
            and all(isinstance(a, str) for a in given)
            and not re.search(r"(?i)\bassum(?:ed|ptions?)\s*\**\s*:", answer)
        ):
            answer += "\n\n**Assumed:** " + "; ".join(given)
    if isinstance(state.result, dict) and (
        trip := energy_sign_problem(flat_numbers(state.result), state.question)
    ):  # after the guardrail, so the warning's own numbers are not checked
        state.flags.append("energy_balance_sign")
        answer += (
            "\n\n**Warning:** this reactor is adiabatic and exothermic, yet the computed "
            f"outlet temperature ({trip[0]:.1f} K) is below the feed ({trip[1]:.1f} K). "
            "The heat-of-reaction sign is probably wrong, so don't trust these numbers."
        )
    if set(state.flags) - {_SOFT_FLAG}:
        confidence: Literal["high", "medium", "low"] = "low"
    elif (
        state.cross_check == "agreed"
        or _SOFT_FLAG in state.flags
        or _invented(state.result, state.question)
    ):
        confidence = "medium"
    else:
        confidence = "high"
    return _final(state, answer, confidence)


_SOFT_FLAG = "check_disagreed"  # the first check disagreed: never high, not low
_CROSS_CHECK_FAILED = (
    "Two different methods gave answers I couldn't reconcile, and the independent "
    "re-check didn't produce a usable result either, so I'm not giving a number I "
    "can't stand behind. Try rephrasing the question, or split it into smaller parts."
)


async def _out_of_budget(state: SolveState, deps: Deps) -> Step:
    """Honest partial answer: no numbers that were not verified."""
    state.flags.append("limit_reached")
    text = (
        "I couldn't finish a verified answer within the limits for one solve "
        "(4 tool steps, 90 seconds), so I'm not giving a number I can't stand behind. "
        "Try rephrasing the question, or split it into smaller parts."
    )
    return _final(state, text, "low", with_numbers=False)


async def _capped(state: SolveState, deps: Deps) -> Step:
    """Spend cap hit (T7): serve a saved answer to the same question, else say so. Never a number."""
    saved = await deps.store.cached(state.question)
    if saved is None:
        state.flags.append("spend_cap")
        return _final(
            state,
            "Today's AI limit is reached, so I can't solve a new question right now. "
            "Try again tomorrow.",
            "low",
            with_numbers=False,
        )
    state.flags.append("cached")
    if saved.get("confidence") == "high":  # an old answer is never re-checked: at most medium
        saved["confidence"] = "medium"
    saved["answer_md"] = (
        "Today's AI limit is reached, so here is a saved answer to the same question:\n\n"
        + saved["answer_md"]
    )
    return Final.model_validate(saved)


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
        answer_md=tidy_markdown(answer_md),
        numbers=numbers,
        figures=state.figures if with_numbers else [],
        diagram_mermaid=state.diagram,
        sources=[Source(**s) for s in state.sources],
        confidence=confidence,
    )


_STEADY_UNITS = {"T": "K", "X": "-", "CA": "mol/m^3", "Da": "-"}


def _strip_sizing(template: str, result: dict[str, Any], question: str) -> None:
    """Sizing outputs computed from defaulted inputs are hidden from the model and the
    answer (they would be invented numbers) unless the question asks for sizing."""
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        return
    kept = drop_sizing_outputs(template, outputs, question)
    if kept is not outputs:
        result["outputs"] = kept
        result.pop("geometry", None)


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
