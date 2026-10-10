"""The agent's tools: exactly six (AGENTS.md rule 6). Anything else is refused.

run_python is not executed here: the server never runs model-written code. It
becomes a run_python step that the browser worker runs. draw_diagram only stores
Mermaid text for the answer. The other four call backend services through ToolImpls;
until those tickets land (NR, S4, D6, Q1) StubTools answers "not available".
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

TOOL_NAMES = (
    "run_python",
    "search_my_notes",
    "web_search",
    "make_quiz",
    "schedule_reminder",
    "draw_diagram",
)
MERMAID_TYPES = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
)
MERMAID_MAX_CHARS = 4000


def _fn(name: str, description: str, props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": list(props),
            },
        },
    }


_STR = {"type": "string"}
TOOL_SCHEMAS: list[dict[str, Any]] = [
    _fn(
        "run_python",
        "Run Python (numpy, scipy, sympy, matplotlib) in the student's browser. "
        "The code must end by setting result = {...}.",
        {"code": _STR},
    ),
    _fn("search_my_notes", "Search the student's uploaded notes.", {"query": _STR}),
    _fn("web_search", "Search the web for cited sources.", {"query": _STR}),
    _fn(
        "make_quiz",
        "Make a short practice quiz on a topic.",
        {"topic": _STR, "n_items": {"type": "integer", "minimum": 1, "maximum": 10}},
    ),
    _fn(
        "schedule_reminder",
        "Schedule a reminder for the student.",
        {"title": _STR, "due_at_utc": {"type": "string", "format": "date-time"}},
    ),
    _fn("draw_diagram", "Attach a Mermaid diagram to the answer.", {"mermaid": _STR}),
]
assert tuple(t["function"]["name"] for t in TOOL_SCHEMAS) == TOOL_NAMES


@dataclass(frozen=True)
class Hit:
    title: str
    text: str
    url: str | None = None


class ToolImpls(Protocol):
    async def search_my_notes(self, user_id: str, query: str) -> list[Hit]: ...
    async def web_search(self, query: str) -> list[Hit]: ...
    async def make_quiz(self, user_id: str, topic: str, n_items: int) -> str: ...
    async def schedule_reminder(
        self, user_id: str, title: str, due_at_utc: str
    ) -> str: ...


class StubTools:
    async def search_my_notes(self, user_id: str, query: str) -> list[Hit]:
        return []

    async def web_search(self, query: str) -> list[Hit]:
        return []

    async def make_quiz(self, user_id: str, topic: str, n_items: int) -> str:
        return "make_quiz is not available yet"

    async def schedule_reminder(self, user_id: str, title: str, due_at_utc: str) -> str:
        return "schedule_reminder is not available yet"


class ToolRefused(ValueError):
    """Unknown tool or bad arguments; the model is told why and may try again."""


def parse_args(name: str, arguments: str) -> dict[str, Any]:
    if name not in TOOL_NAMES:
        raise ToolRefused(f"unknown tool '{name}'; allowed: {', '.join(TOOL_NAMES)}")
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError as err:
        raise ToolRefused(f"{name}: arguments are not valid JSON ({err})") from err
    if not isinstance(args, dict):
        raise ToolRefused(f"{name}: arguments must be a JSON object")
    required = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == name)[
        "function"
    ]["parameters"]["required"]
    missing = [k for k in required if k not in args]
    if missing:
        raise ToolRefused(f"{name}: missing {', '.join(missing)}")
    return args


def check_mermaid(text: str) -> str:
    """Length and diagram type only; the web app sanitises and renders it."""
    text = text.strip()
    if not text or len(text) > MERMAID_MAX_CHARS:
        raise ToolRefused(
            f"draw_diagram: diagram must be 1-{MERMAID_MAX_CHARS} characters"
        )
    if not text.split(None, 1)[0].startswith(MERMAID_TYPES):
        raise ToolRefused(
            f"draw_diagram: first word must be one of {', '.join(MERMAID_TYPES)}"
        )
    return text


def hits_as_data(hits: list[Hit]) -> str:
    """Notes and web text enter prompts as quoted data, never as instructions."""
    items = [{"title": h.title, "url": h.url, "text": h.text[:1500]} for h in hits[:5]]
    return json.dumps(items, ensure_ascii=False)
