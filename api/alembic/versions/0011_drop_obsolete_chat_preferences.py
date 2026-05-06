"""drop obsolete chat preferences

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE user_preferences "
        "SET data = data - ('play' || 'ground') "
        "WHERE data ? ('play' || 'ground')"
    )


def downgrade() -> None:
    pass
