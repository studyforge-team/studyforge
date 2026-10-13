"""app.heartbeats: keep-alive pings (RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "heartbeats",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.Text, nullable=False),
        schema="app",
    )
    op.execute("ALTER TABLE app.heartbeats ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("heartbeats", schema="app")
