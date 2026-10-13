"""app schema: solves, quizzes, llm_calls (RLS on, no policies)"""

from alembic import op

from app.db import metadata

revision = "0001"
down_revision = None
TABLES = ["solves", "quizzes", "llm_calls"]


def upgrade() -> None:
    # alembic_version lives in `app` too, so the schema must exist before it is stamped
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    # ponytail: create from the live metadata; freeze to explicit DDL once the schema changes
    metadata.create_all(op.get_bind())
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
    metadata.drop_all(op.get_bind())
