"""T7 spend guard: total / daily / per-user / per-IP (anonymous only) caps on llm_calls.cost_usd.

The Nebius-console key cap (<=70% of balance until 30 Nov, 95% from 1 Dec) is a human step;
SPEND_CAP_USD is the in-app total cap. When a cap is hit, BudgetExceeded stops the LLM call and
the loop serves a cached answer (see loop._capped).
"""

import ipaddress
import os
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.llm.errors import BudgetExceeded


@dataclass(frozen=True)
class Who:
    user_id: str | None = None
    anon: bool = False
    ip: str | None = None


who: ContextVar[Who] = ContextVar("who", default=Who())  # noqa: B039 (frozen)


def _internal(ip: str) -> bool:
    try:
        return not ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def client_ip(xff: str | None, peer: str | None) -> str | None:
    """Rightmost public X-Forwarded-For entry: the one Render's edge appended. Render's own
    internal hops (10.x) sit right of it; with only those, every student shared one daily
    IP cap (ACC1). Left entries are client-supplied and spoofable, so they are never trusted."""
    parts = [p.strip() for p in (xff or "").split(",") if p.strip()]
    for part in reversed(parts):
        if not _internal(part):
            return part
    return parts[-1] if parts else peer


def _cap(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else None  # invalid -> ValueError at startup, on purpose


@dataclass(frozen=True)
class Caps:
    total: float | None = None
    day: float | None = None
    user: float | None = None
    ip: float | None = None

    @classmethod
    def from_env(cls) -> "Caps":
        return cls(
            _cap("SPEND_CAP_USD"), _cap("DAILY_GLOBAL_USD"),
            _cap("DAILY_USER_USD"), _cap("DAILY_IP_USD"),
        )


# UTC day start as timestamptz; null params compare false -> 0 (no user / no ip known).
# cost_usd is NULL for models without a registry price: those calls count as 0 here.
_SQL = text("""
with d as (select date_trunc('day', now() at time zone 'utc') at time zone 'utc' as t)
select coalesce(sum(cost_usd), 0),
       coalesce(sum(cost_usd) filter (where created_at >= d.t), 0),
       coalesce(sum(cost_usd) filter (where created_at >= d.t and user_id = cast(:u as text)), 0),
       coalesce(sum(cost_usd) filter (where created_at >= d.t and ip = cast(:i as text)), 0)
from app.llm_calls, d
""")


class SpendGuard:
    def __init__(self, engine: AsyncEngine, caps: Caps) -> None:
        self._engine, self._caps = engine, caps

    async def check(self, role: str, model_id: str) -> None:
        c, w = self._caps, who.get()
        if c == Caps():
            return
        async with self._engine.connect() as conn:
            total, day, user, ip = (
                await conn.execute(_SQL, {"u": w.user_id, "i": w.ip})
            ).one()
        for name, spent, cap in (
            ("total", total, c.total), ("daily", day, c.day),
            ("user", user, c.user), ("ip", ip if w.anon else 0, c.ip),
        ):
            if cap is not None and spent >= cap:
                raise BudgetExceeded(f"{name} spend cap reached")
