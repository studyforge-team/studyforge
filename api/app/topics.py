"""Topic results tracker — records per-topic correct/incorrect counts.

Used by ``POST /api/v1/quizzes/{id}/answers`` to maintain the
``app.topic_results`` table, which drives the "Weak topics" section of the
dashboard.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import topic_results


class TopicTracker:
    """Records per-item correctness into ``app.topic_results``."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(
        self,
        user_id: str,
        topic: str,
        correct: bool,
    ) -> None:
        """Insert one row into ``topic_results``."""
        async with self._engine.begin() as conn:
            await conn.execute(
                topic_results.insert().values(
                    user_id=user_id,
                    topic=topic,
                    correct=correct,
                )
            )
