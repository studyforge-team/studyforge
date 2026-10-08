"""Solve state, saved before every step is returned (plan S2: state saved each step).

The loop is DB-free: it reads and writes SolveState through a StateStore. The route
layer uses a Postgres store (row lock per solve); tests and the eval runner (T4) use
InMemoryStore.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class SolveState(BaseModel):
    id: str
    user_id: str
    question: str
    upload_id: str | None = None
    status: Literal["awaiting_confirm", "awaiting_result", "done"] = "awaiting_result"
    kind: Literal["calc", "concept"] | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    steps_used: int = 0  # counted tool steps (max 4)
    started_at: float | None = None  # server clock at the first next_action
    pending_call_id: str | None = None  # native tool-call id of the open run_python
    last_step: dict[str, Any] | None = None  # wire form of the last issued step
    result: Any = None  # last result that passed verify
    verify_failures: int = 0
    cross_check: Literal["none", "pending", "agreed", "disagreed"] = "none"
    first_answer: float | None = None  # answer before the cross-check
    figures: list[str] = Field(default_factory=list)
    diagram: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0


class SolveNotFound(LookupError):
    """Unknown solve id, or a solve that belongs to another user."""


class StateStore(Protocol):
    def lock(self, solve_id: str) -> Any: ...  # async context manager
    async def get(self, solve_id: str) -> SolveState | None: ...
    async def save(self, state: SolveState) -> None: ...


class InMemoryStore:
    def __init__(self) -> None:
        self.states: dict[str, SolveState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def lock(self, solve_id: str) -> AsyncIterator[None]:
        async with self._locks.setdefault(solve_id, asyncio.Lock()):
            yield

    async def get(self, solve_id: str) -> SolveState | None:
        state = self.states.get(solve_id)
        return state.model_copy(deep=True) if state else None

    async def save(self, state: SolveState) -> None:
        self.states[state.id] = state.model_copy(deep=True)
