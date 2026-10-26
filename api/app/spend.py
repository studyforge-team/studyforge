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


# Cloudflare sits in front of Render: its edge address follows the student's in the chain.
# Published ranges, https://www.cloudflare.com/ips/ (checked 26 Oct 2026).
_CLOUDFLARE = tuple(ipaddress.ip_network(n) for n in (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
))  # fmt: skip


def _internal(ip: str) -> bool:
    """A proxy hop, not a student: Render's internal network or a Cloudflare edge."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not addr.is_global or any(addr in n for n in _CLOUDFLARE if n.version == addr.version)


def client_ip(xff: str | None, peer: str | None) -> str | None:
    """Rightmost X-Forwarded-For entry that is not a proxy hop: the student's address as
    Cloudflare received it. Render's internal hops (10.x) and Cloudflare's edge (172.71.x
    in the 26 Oct logs) sit right of it; keyed on those, every student shared one daily IP
    cap (ACC1). Left entries are client-supplied and spoofable, so they are never trusted."""
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
