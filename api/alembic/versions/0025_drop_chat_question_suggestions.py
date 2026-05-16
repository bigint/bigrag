"""drop chat question suggestions

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE user_preferences "
        "SET data = jsonb_set(data, '{chat}', (data->'chat') - 'question_suggestions') "
        "WHERE jsonb_typeof(data->'chat') = 'object' "
        "AND (data->'chat') ? 'question_suggestions'"
    )


def downgrade() -> None:
    pass
