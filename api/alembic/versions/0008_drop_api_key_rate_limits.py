"""drop API key rate limit configuration

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE api_keys DROP COLUMN IF EXISTS rate_limits")


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE api_keys
        ADD COLUMN IF NOT EXISTS rate_limits jsonb NOT NULL DEFAULT '{}'::jsonb
        """
    )
