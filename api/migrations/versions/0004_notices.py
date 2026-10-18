"""app.notices: text a student pastes or shares into StudyForge (D1; RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "notices",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.create_index("ix_notices_user_created", "notices", ["user_id", "created_at"], schema="app")
    op.execute("ALTER TABLE app.notices ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("notices", schema="app")
