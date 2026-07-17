"""attribute runs and agent calls to accounts

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-07-17 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows stay NULL — unattributed, never guessed.
    op.add_column("durable_runs", sa.Column("account_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "durable_runs_account_id_fkey",
        "durable_runs",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("agent_calls", sa.Column("account_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "agent_calls_account_id_fkey",
        "agent_calls",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "agent_calls_account_finished_idx", "agent_calls", ["account_id", "finished_at"]
    )


def downgrade() -> None:
    op.drop_index("agent_calls_account_finished_idx", table_name="agent_calls")
    op.drop_constraint("agent_calls_account_id_fkey", "agent_calls", type_="foreignkey")
    op.drop_column("agent_calls", "account_id")
    op.drop_constraint("durable_runs_account_id_fkey", "durable_runs", type_="foreignkey")
    op.drop_column("durable_runs", "account_id")
