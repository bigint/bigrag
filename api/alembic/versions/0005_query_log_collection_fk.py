"""query_log: add collection_id FK with ON DELETE CASCADE

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "query_log",
        sa.Column(
            "collection_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "query_log_collection_id_fkey",
        "query_log",
        "collections",
        ["collection_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_query_log_collection_id", "query_log", ["collection_id"])
    op.execute(
        """
        UPDATE query_log
           SET collection_id = c.id
          FROM collections c
         WHERE c.name = query_log.collection_name
           AND query_log.collection_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_query_log_collection_id", table_name="query_log")
    op.drop_constraint("query_log_collection_id_fkey", "query_log", type_="foreignkey")
    op.drop_column("query_log", "collection_id")
