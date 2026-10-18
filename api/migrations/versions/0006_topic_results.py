"""app.topic_results: per-topic right/wrong from quizzes and check-ins (D8; RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "topic_results",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("correct", sa.Boolean, nullable=False),
        sa.Column("source", sa.Text, nullable=False),  # 'quiz' | 'checkin'
        sa.Column("ref", sa.Text, nullable=False),  # quiz id or check-in job id
        sa.Column("item", sa.Integer, nullable=False),  # quiz item index; 0 for a check-in
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "source", "ref", "item", name="uq_topic_results_once"),
        schema="app",
    )
    op.create_index("ix_topic_results_user_created", "topic_results", ["user_id", "created_at"], schema="app")
    op.execute("ALTER TABLE app.topic_results ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN "
        "REVOKE ALL ON app.topic_results FROM anon, authenticated; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_table("topic_results", schema="app")
