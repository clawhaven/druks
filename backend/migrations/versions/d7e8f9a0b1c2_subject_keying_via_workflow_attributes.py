"""subject keying via workflow attributes

Revision ID: d7e8f9a0b1c2
Revises: c9d0e1f2a3b4
Create Date: 2026-07-13 09:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from dbos import run_dbos_database_migrations
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # DBOS owns workflow_status and adds its attributes column in its own
    # migrations, which normally run at app launch — after this history on an
    # upgrading host. Run them first so the backfill always has the column.
    url = op.get_bind().engine.url.render_as_string(hide_password=False)
    run_dbos_database_migrations(
        url.replace("postgresql+psycopg://", "postgresql://", 1), schema="dbos"
    )
    # Every run's subject/extension moves onto its workflow as custom attributes,
    # the shape start() stamps for new runs: subject_id always a string.
    op.execute(
        """
        UPDATE dbos.workflow_status ws
        SET attributes = coalesce(ws.attributes, '{}'::jsonb)
            || CASE WHEN r.subject IS NULL THEN '{}'::jsonb
                    ELSE jsonb_build_object(
                        'subject_type', r.subject->>'type',
                        'subject_id', r.subject->>'id') END
            || CASE WHEN r.extension IS NULL THEN '{}'::jsonb
                    ELSE jsonb_build_object('extension', r.extension) END
        FROM durable_runs r
        WHERE ws.workflow_uuid = r.id
          AND (r.subject IS NOT NULL OR r.extension IS NOT NULL)
        """
    )
    op.drop_column("durable_runs", "input")
    op.drop_column("durable_runs", "subject")
    op.drop_column("durable_runs", "extension")


def downgrade() -> None:
    op.add_column("durable_runs", sa.Column("extension", sa.String(), nullable=True))
    op.add_column(
        "durable_runs",
        sa.Column("subject", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "durable_runs",
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Rebuild subject/extension from the attributes; the subject id comes back as
    # a string (attributes never kept the original type). Workflow inputs are not
    # recoverable from attributes, so input restores as {}.
    op.execute(
        """
        UPDATE durable_runs r
        SET subject = CASE WHEN ws.attributes ? 'subject_type'
                THEN jsonb_build_object(
                    'type', ws.attributes->>'subject_type',
                    'id', ws.attributes->>'subject_id') END,
            extension = ws.attributes->>'extension'
        FROM dbos.workflow_status ws
        WHERE ws.workflow_uuid = r.id AND ws.attributes IS NOT NULL
        """
    )
    op.execute("UPDATE durable_runs SET input = '{}'::jsonb")
    op.alter_column("durable_runs", "input", nullable=False)
