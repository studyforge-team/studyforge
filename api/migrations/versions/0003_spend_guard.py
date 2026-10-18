"""app.llm_calls: who made the call (user_id, ip) + created_at index for the T7 spend queries"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("user_id", sa.Text), schema="app")
    op.add_column("llm_calls", sa.Column("ip", sa.Text), schema="app")
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls", schema="app")
    op.drop_column("llm_calls", "ip", schema="app")
    op.drop_column("llm_calls", "user_id", schema="app")
