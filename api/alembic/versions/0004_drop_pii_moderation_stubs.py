"""drop redact_pii and moderation_enabled stub columns

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-26

Both columns existed but the underlying features were never wired:
- ``redact_pii`` set a metadata flag that nothing read; the redaction
  service was deleted in an earlier commit.
- ``moderation_enabled`` ran moderation on raw upload bytes (mostly
  binary noise) and only checked the first 10 KB — trivially bypassable.

Both are removed wholesale rather than fixed.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("collections", "redact_pii")
    op.drop_column("collections", "moderation_enabled")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column(
        "collections",
        sa.Column("redact_pii", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "collections",
        sa.Column(
            "moderation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
