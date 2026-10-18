"""app schema: solves, quizzes, llm_calls (RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
TABLES = ["solves", "quizzes", "llm_calls"]
S = "app"


def _ts(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    # alembic_version lives in `app` too, so the schema must exist before it is stamped
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "solves",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False, index=True),
        sa.Column("state", JSONB, nullable=False),
        _ts("updated_at"),
        schema=S,
    )
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False, index=True),
        sa.Column("quiz", JSONB, nullable=False),
        _ts("created_at"),
        schema=S,
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("solve_id", sa.Text),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("ok", sa.Boolean, nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("prompt_tokens", sa.Integer, nullable=False),
        sa.Column("completion_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Double),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        _ts("created_at"),
        schema=S,
    )
    for t in TABLES:
        op.execute(f"ALTER TABLE app.{t} ENABLE ROW LEVEL SECURITY")
    # anon/authenticated exist only on Supabase
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            REVOKE ALL ON SCHEMA app FROM anon, authenticated;
        END IF; END $$"""
    )


def downgrade() -> None:
    # schema stays: alembic_version still lives in it until base is stamped
    for t in reversed(TABLES):
        op.drop_table(t, schema=S)
