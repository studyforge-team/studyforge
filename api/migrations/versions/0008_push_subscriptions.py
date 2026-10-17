"""app.push_subscriptions: one row per phone/browser that turned on reminders (D1b; RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False, index=True),
        sa.Column("endpoint", sa.Text, nullable=False, unique=True),
        sa.Column("p256dh", sa.Text, nullable=False),
        sa.Column("auth", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.execute("ALTER TABLE app.push_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN "
        "REVOKE ALL ON app.push_subscriptions FROM anon, authenticated; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions", schema="app")
