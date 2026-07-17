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
    # Pre-release: existing rows adopt the system account.
    op.execute(
        "INSERT INTO accounts (id, email, created_at) VALUES ('system', 'system', now()) "
        "ON CONFLICT (id) DO NOTHING"
    )
    for table in ("durable_runs", "agent_calls"):
        op.add_column(table, sa.Column("account_id", sa.String(), nullable=True))
        op.execute(f"UPDATE {table} SET account_id = 'system'")
        op.alter_column(table, "account_id", nullable=False)
        op.create_foreign_key(
            f"{table}_account_id_fkey",
            table,
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
    for table in ("agent_calls", "durable_runs"):
        op.drop_constraint(f"{table}_account_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "account_id")
