"""app.note_chunks: one row per page of a student's notes PDF, full-text searchable (NR; RLS on, no policies)"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    # Explicit DDL, frozen: later changes go in new revisions, never edit this one.
    op.create_table(
        "note_chunks",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("upload_id", sa.Text, nullable=False),
        sa.Column("page", sa.Integer, nullable=False),  # 1-based slide/page
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("tsv", sa.dialects.postgresql.TSVECTOR, sa.Computed("to_tsvector('english', text)", persisted=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "upload_id", "page", name="uq_note_chunks_page"),
        schema="app",
    )
    op.create_index("ix_note_chunks_tsv", "note_chunks", ["tsv"], schema="app", postgresql_using="gin")
    op.create_index("ix_note_chunks_user", "note_chunks", ["user_id"], schema="app")
    op.execute("ALTER TABLE app.note_chunks ENABLE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN "
        "REVOKE ALL ON app.note_chunks FROM anon, authenticated; END IF; END $$"
    )


def downgrade() -> None:
    op.drop_table("note_chunks", schema="app")
