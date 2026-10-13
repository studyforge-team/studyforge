"""app.jobs: reminder queue drained by the keep-alive ping (RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("dedupe_key", sa.Text, nullable=False, unique=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="app",
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"], schema="app")
    op.create_index(
        "ix_jobs_due_unsent", "jobs", ["due_at"], schema="app",
        postgresql_where=sa.text("sent_at IS NULL"),
    )
    op.execute("ALTER TABLE app.jobs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("jobs", schema="app")
