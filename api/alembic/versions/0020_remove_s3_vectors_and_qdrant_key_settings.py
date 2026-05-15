"""remove s3 vectors and qdrant key settings

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM instance_settings
        WHERE key IN (
            'qdrant_api_key',
            's3_vectors_access_key_id',
            's3_vectors_bucket',
            's3_vectors_index_prefix',
            's3_vectors_region',
            's3_vectors_secret_access_key'
        )
        """
    )


def downgrade() -> None:
    pass
