"""D8: weak-topic memory. One row per answered item; weak = accuracy < 0.7 over the last 90 days."""

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_INSERT = text(
    "INSERT INTO app.topic_results (user_id, topic, correct, source, ref, item) "
    "VALUES (:u, :t, :c, :s, :r, :i) ON CONFLICT (user_id, source, ref, item) DO NOTHING"
)
# group on a case/space-folded key; show the most recent spelling
_KEY = r"lower(btrim(regexp_replace(topic, '\s+', ' ', 'g')))"
_WEAK = text(
    "SELECT (array_agg(topic ORDER BY created_at DESC, id DESC))[1] AS topic, count(*) AS attempts, "
    "count(*) FILTER (WHERE correct) AS correct FROM app.topic_results "
    "WHERE user_id = :u AND created_at > now() - interval '90 days' "
    f"GROUP BY {_KEY} "
    "HAVING count(*) FILTER (WHERE correct) < 0.7 * count(*) "
    f"ORDER BY count(*) FILTER (WHERE correct) * 1.0 / count(*), count(*) DESC, {_KEY} LIMIT :n"
)


def clean(topic: str) -> str:
    return re.sub(r"\s+", " ", topic).strip()[:80]


async def record(
    conn: AsyncConnection, user_id: str, source: str, ref: str, items: list[tuple[int, str, bool]]
) -> int:
    """Insert (item index, topic, correct); replays are ignored. Returns rows newly inserted."""
    n = 0
    for i, topic, correct in items:
        res = await conn.execute(_INSERT, {"u": user_id, "t": clean(topic), "c": correct,
                                           "s": source, "r": ref, "i": i})
        n += res.rowcount
    return n


async def weak_topics(conn: AsyncConnection, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = (await conn.execute(_WEAK, {"u": user_id, "n": limit})).mappings().all()
    return [{"topic": r["topic"], "attempts": r["attempts"], "correct": r["correct"]} for r in rows]
