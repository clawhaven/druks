"""fallback account replaces the default login

Revision ID: b5c6d7e8f9a0
Revises: a8060465d9ed
Create Date: 2026-07-16 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "a8060465d9ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("fallback_account_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "user_settings_fallback_account_id_fkey",
        "user_settings",
        "accounts",
        ["fallback_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Carry the semantics over: the default login's account — else the oldest
    # account (uuid7 ids sort by creation) — becomes the fallback. The
    # singleton row may not exist yet on an install nobody configured.
    op.execute(
        "INSERT INTO user_settings (id, timezone, updated_at) VALUES (1, 'UTC', now()) "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        """
        UPDATE user_settings SET fallback_account_id = COALESCE(
            (SELECT account_id FROM harness_logins WHERE is_default LIMIT 1),
            (SELECT id FROM accounts ORDER BY id LIMIT 1)
        )
        WHERE id = 1
        """
    )
    op.drop_index("harness_logins_default_idx", table_name="harness_logins")
    op.drop_column("harness_logins", "is_default")


def downgrade() -> None:
    op.add_column(
        "harness_logins",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE harness_logins SET is_default = true
        WHERE account_id = (SELECT fallback_account_id FROM user_settings WHERE id = 1)
        """
    )
    op.create_index(
        "harness_logins_default_idx",
        "harness_logins",
        ["harness"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.drop_constraint(
        "user_settings_fallback_account_id_fkey", "user_settings", type_="foreignkey"
    )
    op.drop_column("user_settings", "fallback_account_id")
