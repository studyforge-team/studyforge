"""Deadline reminders: T-3d, T-1d and 08:00 IST on the day, stored as rows in app.jobs.

ponytail: no APScheduler. Render free sleeps, so an in-process scheduler can't be trusted;
the keep-alive ping (GitHub Actions every 10 min + UptimeRobot every 5 min) is the clock and
/keepalive drains due jobs, so a reminder is at most ~10 min late. Fine for reminders.
Reminder text only LINKS to the prep pack; it is never computed here.
"""

import hashlib
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import jobs

# ponytail: every student is IST (plan: "IST in, UTC stored"); a per-user timezone is a later change
# fixed UTC+5:30 (India has no DST) instead of zoneinfo: Windows has no tzdata and we add no deps
IST = timezone(timedelta(hours=5, minutes=30))
LABELS = {"t-3d": "3 days before", "t-1d": "1 day before", "morning": "morning of"}
WHEN = {"t-3d": "in 3 days", "t-1d": "tomorrow", "morning": "today"}


def offsets(deadline_utc: datetime, now_utc: datetime) -> list[tuple[str, datetime]]:
    morning = datetime.combine(deadline_utc.astimezone(IST).date(), time(8), IST)
    slots = [
        ("t-3d", deadline_utc - timedelta(days=3)),
        ("t-1d", deadline_utc - timedelta(days=1)),
        ("morning", morning),
    ]
    return [(s, t) for s, t in slots if now_utc < t < deadline_utc]


def _key(user_id: str, title: str, deadline_utc: datetime) -> str:
    raw = f"{user_id}|{' '.join(title.lower().split())}|{deadline_utc.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def schedule(
    engine: AsyncEngine, user_id: str, title: str, deadline_utc: datetime, now_utc: datetime
) -> int:
    """Insert one job per remaining slot; re-scheduling the same task inserts nothing."""
    key = _key(user_id, title, deadline_utc)
    inserted = 0
    async with engine.begin() as conn:
        for slot, due in offsets(deadline_utc, now_utc):
            stmt = insert(jobs).values(
                user_id=user_id, kind="reminder", dedupe_key=f"{key}:{slot}", due_at=due,
                payload={"title": title, "deadline_utc": deadline_utc.isoformat(),
                         "slot": slot, "prep": f"/#prep/{key}"},
            ).on_conflict_do_nothing(index_elements=["dedupe_key"])
            inserted += (await conn.execute(stmt)).rowcount
    return inserted


async def drain(engine: AsyncEngine, now_utc: datetime, limit: int = 50) -> list[dict[str, Any]]:
    """Mark due jobs sent and return them. SKIP LOCKED: concurrent pingers never double-send.
    Delivery today = the in-app inbox (sent jobs ARE the inbox); push is D1b, later."""
    stmt = text(
        "UPDATE app.jobs SET sent_at = :now WHERE id IN ("
        "SELECT id FROM app.jobs WHERE sent_at IS NULL AND due_at <= :now "
        "ORDER BY due_at LIMIT :limit FOR UPDATE SKIP LOCKED) "
        "RETURNING id, user_id, payload, due_at"
    )
    async with engine.begin() as conn:
        rows = (await conn.execute(stmt, {"now": now_utc, "limit": limit})).mappings().all()
    return [dict(r) for r in rows]


def reminder_text(payload: dict[str, Any]) -> str:
    due = datetime.fromisoformat(payload["deadline_utc"]).astimezone(IST)
    when = f"{due:%a} {due.day} {due:%b}, {due:%H:%M} IST"
    return (f"Reminder: {payload['title']} is due {WHEN[payload['slot']]} ({when}). "
            f"Your prep pack: {payload['prep']}")


async def schedule_reminder_tool(
    engine: AsyncEngine, user_id: str, title: str, due_at_utc: str, now_utc: datetime | None = None
) -> str:
    """Body for ToolImpls.schedule_reminder once get_deps wires a DB-backed tools class."""
    try:
        deadline = datetime.fromisoformat(due_at_utc)
    except ValueError:
        return "Could not read due_at_utc; send an ISO 8601 timestamp with a timezone."
    if deadline.tzinfo is None:
        return "due_at_utc must include a timezone (e.g. 2026-10-30T17:00:00Z); nothing scheduled."
    now = now_utc or datetime.now(UTC)
    if deadline <= now:
        return "That deadline is already in the past; nothing scheduled."
    slots = offsets(deadline, now)
    if not slots:
        return "The deadline is too close for any reminder slot; nothing scheduled."
    await schedule(engine, user_id, title, deadline, now)
    return f"scheduled {len(slots)} reminders ({', '.join(LABELS[s] for s, _ in slots)})"
