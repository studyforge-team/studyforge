"""Cost log rows and the hooks the backend plugs in (DB recorder, spend guard)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from app.llm.registry import ResolvedModel


@dataclass(frozen=True)
class CallRecord:
    """One row of llm_calls: written for every attempt, failed ones included."""

    role: str
    model_id: str
    ok: bool
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None  # None while the model's price is not in the registry
    latency_ms: int
    solve_id: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CostRecorder(Protocol):
    async def record(self, row: CallRecord) -> None: ...


class BudgetGuard(Protocol):
    """Called before every request; raises BudgetExceeded to stop it (T7)."""

    async def check(self, role: str, model_id: str) -> None: ...


class InMemoryCostRecorder:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, row: CallRecord) -> None:
        self.records.append(row)


class NoBudgetGuard:
    async def check(self, role: str, model_id: str) -> None:
        return None


def price(
    model: ResolvedModel, prompt_tokens: int, completion_tokens: int
) -> float | None:
    if model.input_usd_per_m is None or model.output_usd_per_m is None:
        return None
    return (
        prompt_tokens * model.input_usd_per_m
        + completion_tokens * model.output_usd_per_m
    ) / 1e6
