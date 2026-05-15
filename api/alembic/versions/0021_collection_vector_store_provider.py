"""store vector provider per collection

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collections",
        sa.Column(
            "vector_store_provider",
            sa.Text(),
            server_default="qdrant",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE collections
        SET vector_store_provider = COALESCE(
            (
                SELECT value #>> '{}'
                FROM instance_settings
                WHERE key = 'vector_store_provider'
                LIMIT 1
            ),
            'qdrant'
        )
        """
    )
    op.create_check_constraint(
        "collections_vector_store_provider_check",
        "collections",
        "vector_store_provider IN ('qdrant', 'turbopuffer')",
    )
    op.execute("DELETE FROM instance_settings WHERE key = 'vector_store_provider'")


def downgrade() -> None:
    op.drop_constraint(
        "collections_vector_store_provider_check",
        "collections",
        type_="check",
    )
    op.drop_column("collections", "vector_store_provider")
