"""drop S3 ingestion jobs

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from bigrag.services.crypto import EncryptedString

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS s3_ingest_jobs")


def downgrade() -> None:
    op.create_table(
        "s3_ingest_jobs",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("collection_name", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), server_default="", nullable=False),
        sa.Column("region", sa.Text(), server_default="us-east-1", nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("access_key", EncryptedString(), nullable=True),
        sa.Column("secret_key", EncryptedString(), nullable=True),
        sa.Column("no_sign_request", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "file_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("total_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_ingested", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
            "status IN ('pending', 'listing', 'ingesting', 'complete', 'failed')",
            name="s3_ingest_jobs_status_check",
        ),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_s3_ingest_jobs_status", "s3_ingest_jobs", ["status"], unique=False)
    op.create_index(
        "idx_s3_ingest_jobs_collection_id",
        "s3_ingest_jobs",
        ["collection_id"],
        unique=False,
    )
