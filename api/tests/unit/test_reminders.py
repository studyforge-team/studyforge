import asyncio
from datetime import UTC, datetime, timedelta

from app.reminders import offsets, reminder_text, schedule_reminder_tool

DEADLINE = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)  # Fri 30 Oct 22:30 IST
NOW = datetime(2026, 10, 20, tzinfo=UTC)


def z(d: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, d, h, m, tzinfo=UTC)


def test_offsets() -> None:
    assert offsets(DEADLINE, NOW) == [("t-3d", z(27, 17)), ("t-1d", z(29, 17)), ("morning", z(30, 2, 30))]
    assert [s for s, _ in offsets(DEADLINE, z(28, 0))] == ["t-1d", "morning"]
    # 07:00 IST deadline: 08:00 IST that day is after it, so no morning slot
    early = datetime(2026, 10, 30, 1, 30, tzinfo=UTC)
    assert [s for s, _ in offsets(early, NOW)] == ["t-3d", "t-1d"]


def test_text() -> None:
    p = {"title": "OS exam", "deadline_utc": DEADLINE.isoformat(), "prep": "/#prep/abc"}
    for slot, word in (("t-3d", "in 3 days"), ("t-1d", "tomorrow"), ("morning", "today")):
        t = reminder_text(p | {"slot": slot})
        assert f"OS exam is due {word} (Fri 30 Oct, 22:30 IST)" in t and t.endswith("/#prep/abc")


def test_tool_refuses_bad_times() -> None:
    # engine is never touched on a refusal, so None is fine
    run = lambda ts: asyncio.run(schedule_reminder_tool(None, "u", "t", ts, NOW))  # type: ignore[arg-type]
    assert "timezone" in run("2026-10-30T17:00:00")
    assert "past" in run((NOW - timedelta(days=1)).isoformat())
    assert "ISO" in run("tomorrow")


def test_checkin_text() -> None:
    from app.reminders import checkin_text
    p = {"title": "OS exam", "prep": "/#prep/abc"}
    assert checkin_text(p, 7) == ("Did you finish OS exam? Answer one quick question to check: "
                                  "/#prep/abc?checkin=7")
