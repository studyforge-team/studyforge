"""app.quiz_attempts: one row per saved quiz result, for the per-topic progress graph (T4; RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("quiz_id", sa.Text, nullable=False),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("score", sa.Float(24), nullable=False),
        sa.Column("total", sa.Float(24), nullable=False),
        sa.Column("marks_per_q", sa.Float(24), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.create_index("ix_quiz_attempts_user_topic", "quiz_attempts", ["user_id", "topic", "created_at"], schema="app")
    op.execute("ALTER TABLE app.quiz_attempts ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN "
        "REVOKE ALL ON app.quiz_attempts FROM anon, authenticated; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_table("quiz_attempts", schema="app")
