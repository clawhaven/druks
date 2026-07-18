"""usage scrapes per account

Revision ID: ccebfa4ee1e2
Revises: c6d7e8f9a0b1
Create Date: 2026-07-18 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ccebfa4ee1e2"
down_revision: str | Sequence[str] | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Scrapes are an ephemeral poll cache (stale after 24h); pre-account rows
    # describe a login nobody owns — drop them instead of guessing.
    op.execute("DELETE FROM usage_scrapes")
    op.add_column("usage_scrapes", sa.Column("account_id", sa.String(), nullable=False))
    op.create_foreign_key(
        "usage_scrapes_account_id_fkey",
        "usage_scrapes",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_index("usage_scrapes_harness_time_idx", table_name="usage_scrapes")
    op.create_index(
        "usage_scrapes_account_harness_time_idx",
        "usage_scrapes",
        ["account_id", "harness", "scraped_at"],
    )


def downgrade() -> None:
    op.drop_index("usage_scrapes_account_harness_time_idx", table_name="usage_scrapes")
    op.create_index("usage_scrapes_harness_time_idx", "usage_scrapes", ["harness", "scraped_at"])
    op.drop_constraint("usage_scrapes_account_id_fkey", "usage_scrapes", type_="foreignkey")
    op.drop_column("usage_scrapes", "account_id")
