"""add composite indexes for admin list views

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_documents_collection_created_at",
        "documents",
        ["collection_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_documents_collection_status_created_at",
        "documents",
        ["collection_id", "status", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_access_log_actor_created_at",
        "access_log",
        ["actor_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_access_log_action_created_at",
        "access_log",
        ["action", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_access_log_collection_created_at",
        "access_log",
        ["collection_name", sa.literal_column("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_access_log_collection_created_at", table_name="access_log")
    op.drop_index("idx_access_log_action_created_at", table_name="access_log")
    op.drop_index("idx_access_log_actor_created_at", table_name="access_log")
    op.drop_index("idx_documents_collection_status_created_at", table_name="documents")
    op.drop_index("idx_documents_collection_created_at", table_name="documents")
