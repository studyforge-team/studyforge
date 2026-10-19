"""0009: Create quiz_attempts table (T4).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("quiz_id", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column(
            "marks_per_q",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="app",
    )
    op.create_index(
        "ix_quiz_attempts_user_topic",
        "quiz_attempts",
        ["user_id", "topic", "created_at"],
        schema="app",
    )

    # Row-level security — same pattern as 0008_push_subscriptions
    op.execute("ALTER TABLE app.quiz_attempts ENABLE ROW LEVEL SECURITY")
    op.execute(
        "REVOKE ALL ON TABLE app.quiz_attempts FROM anon, authenticated"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quiz_attempts_user_topic",
        table_name="quiz_attempts",
        schema="app",
    )
    op.drop_table("quiz_attempts", schema="app")
