"""upload sessions

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("collection_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="preparing", nullable=False),
        sa.Column("total_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("uploaded_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("queued_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("canceled_files", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('preparing', 'uploading', 'ingesting', 'complete', 'failed', 'canceled')",
            name="upload_sessions_status_check",
        ),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_upload_sessions_collection_created",
        "upload_sessions",
        ["collection_id", "created_at"],
        unique=False,
    )
    op.create_index("idx_upload_sessions_status", "upload_sessions", ["status"], unique=False)
    op.create_table(
        "upload_session_items",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("client_item_id", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), server_default="", nullable=False),
        sa.Column("file_size", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'complete', 'failed', 'canceled')",
            name="upload_session_items_status_check",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["upload_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "client_item_id", name="uq_upload_items_session_client"),
    )
    op.create_index(
        "idx_upload_session_items_document",
        "upload_session_items",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "idx_upload_session_items_session",
        "upload_session_items",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "idx_upload_session_items_status",
        "upload_session_items",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_upload_session_items_status", table_name="upload_session_items")
    op.drop_index("idx_upload_session_items_session", table_name="upload_session_items")
    op.drop_index("idx_upload_session_items_document", table_name="upload_session_items")
    op.drop_table("upload_session_items")
    op.drop_index("idx_upload_sessions_status", table_name="upload_sessions")
    op.drop_index("idx_upload_sessions_collection_created", table_name="upload_sessions")
    op.drop_table("upload_sessions")
