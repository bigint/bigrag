"""add (created_at desc, id) composite indexes for keyset pagination

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_audit_log_created_at_id",
        "audit_log",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "idx_access_log_created_at_id",
        "access_log",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "idx_webhook_deliveries_webhook_created_at_id",
        "webhook_deliveries",
        [
            "webhook_id",
            sa.literal_column("created_at DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
    )
    op.create_index(
        "idx_documents_collection_created_at_id",
        "documents",
        [
            "collection_id",
            sa.literal_column("created_at DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_documents_collection_created_at_id", table_name="documents")
    op.drop_index(
        "idx_webhook_deliveries_webhook_created_at_id",
        table_name="webhook_deliveries",
    )
    op.drop_index("idx_access_log_created_at_id", table_name="access_log")
    op.drop_index("idx_audit_log_created_at_id", table_name="audit_log")
