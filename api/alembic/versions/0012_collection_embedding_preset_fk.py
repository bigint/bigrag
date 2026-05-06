"""collection embedding preset fk

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collections",
        sa.Column("embedding_preset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "collections_embedding_preset_id_fkey",
        "collections",
        "embedding_presets",
        ["embedding_preset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "idx_collections_embedding_preset_id",
        "collections",
        ["embedding_preset_id"],
    )

    op.execute(
        sa.text(
            """
            UPDATE collections AS c
            SET embedding_preset_id = matched.preset_id
            FROM (
                SELECT c.id AS collection_id, p.id AS preset_id
                FROM collections c
                JOIN embedding_presets p
                  ON p.provider = c.embedding_provider
                 AND p.model = c.embedding_model
                 AND p.dimension = c.dimension
                 AND p.base_url IS NOT DISTINCT FROM c.embedding_base_url
                WHERE c.embedding_preset_id IS NULL
                GROUP BY c.id, p.id
            ) AS matched
            WHERE c.id = matched.collection_id
              AND (
                  SELECT COUNT(*)
                  FROM embedding_presets pp
                  WHERE pp.provider = c.embedding_provider
                    AND pp.model = c.embedding_model
                    AND pp.dimension = c.dimension
                    AND pp.base_url IS NOT DISTINCT FROM c.embedding_base_url
              ) = 1
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_collections_embedding_preset_id", table_name="collections")
    op.drop_constraint(
        "collections_embedding_preset_id_fkey",
        "collections",
        type_="foreignkey",
    )
    op.drop_column("collections", "embedding_preset_id")
