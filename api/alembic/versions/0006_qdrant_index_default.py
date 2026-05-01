"""switch vector index default to qdrant hnsw

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "collections",
        "index_type",
        server_default="HNSW",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.execute("UPDATE collections SET index_type = 'HNSW' WHERE index_type <> 'HNSW'")


def downgrade() -> None:
    op.alter_column(
        "collections",
        "index_type",
        server_default=None,
        existing_type=sa.Text(),
        existing_nullable=False,
    )
