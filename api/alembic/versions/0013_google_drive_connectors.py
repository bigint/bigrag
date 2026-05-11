"""google drive connectors

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from rag_computer.services.crypto import EncryptedString

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_provider_configs",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("client_id", sa.Text(), server_default="", nullable=False),
        sa.Column("client_secret", EncryptedString(), nullable=True),
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
            "provider IN ('google_drive')",
            name="connector_provider_configs_provider_check",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )
    op.create_index(
        "idx_connector_provider_configs_provider",
        "connector_provider_configs",
        ["provider"],
        unique=False,
    )

    op.create_table(
        "connector_accounts",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_email", sa.Text(), nullable=True),
        sa.Column("access_token", EncryptedString(), nullable=True),
        sa.Column("refresh_token", EncryptedString(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("oauth_state", sa.Text(), nullable=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
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
            "provider IN ('google_drive')",
            name="connector_accounts_provider_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'connected', 'needs_reauth', 'revoked')",
            name="connector_accounts_status_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_connector_accounts_user_provider"),
    )
    op.create_index(
        "idx_connector_accounts_user_provider",
        "connector_accounts",
        ["user_id", "provider"],
        unique=False,
    )

    op.create_table(
        "connector_sources",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("collection_name", sa.Text(), nullable=False),
        sa.Column("root_id", sa.Text(), nullable=False),
        sa.Column("root_name", sa.Text(), nullable=False),
        sa.Column("root_mime_type", sa.Text(), server_default="", nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="idle", nullable=False),
        sa.Column("schedule_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "sync_interval_hours", sa.Integer(), server_default=sa.text("24"), nullable=False
        ),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
            "provider IN ('google_drive')",
            name="connector_sources_provider_check",
        ),
        sa.CheckConstraint(
            "source_type IN ('file', 'folder')",
            name="connector_sources_source_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('idle', 'syncing', 'needs_reauth', 'error')",
            name="connector_sources_status_check",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["connector_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "collection_id",
            "root_id",
            name="uq_connector_sources_account_collection_root",
        ),
    )
    op.create_index(
        "idx_connector_sources_account_id",
        "connector_sources",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "idx_connector_sources_collection_id",
        "connector_sources",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        "idx_connector_sources_next_sync",
        "connector_sources",
        ["next_sync_at"],
        unique=False,
    )

    op.create_table(
        "connector_sync_jobs",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("started_by", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_created", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "details",
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
            "provider IN ('google_drive')",
            name="connector_sync_jobs_provider_check",
        ),
        sa.CheckConstraint(
            "trigger IN ('initial', 'manual', 'scheduled')",
            name="connector_sync_jobs_trigger_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'failed')",
            name="connector_sync_jobs_status_check",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["connector_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["started_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_connector_sync_jobs_source_created",
        "connector_sync_jobs",
        ["source_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_connector_sync_jobs_status",
        "connector_sync_jobs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "connector_documents",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("remote_id", sa.Text(), nullable=False),
        sa.Column("remote_name", sa.Text(), nullable=False),
        sa.Column("remote_mime_type", sa.Text(), server_default="", nullable=False),
        sa.Column("remote_checksum", sa.Text(), nullable=True),
        sa.Column("remote_version", sa.Text(), nullable=True),
        sa.Column("remote_modified_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("web_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["connector_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "remote_id", name="uq_connector_documents_source_remote"),
    )
    op.create_index(
        "idx_connector_documents_document_id",
        "connector_documents",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "idx_connector_documents_source_remote",
        "connector_documents",
        ["source_id", "remote_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_connector_documents_source_remote", table_name="connector_documents")
    op.drop_index("idx_connector_documents_document_id", table_name="connector_documents")
    op.drop_table("connector_documents")

    op.drop_index("idx_connector_sync_jobs_status", table_name="connector_sync_jobs")
    op.drop_index("idx_connector_sync_jobs_source_created", table_name="connector_sync_jobs")
    op.drop_table("connector_sync_jobs")

    op.drop_index("idx_connector_sources_next_sync", table_name="connector_sources")
    op.drop_index("idx_connector_sources_collection_id", table_name="connector_sources")
    op.drop_index("idx_connector_sources_account_id", table_name="connector_sources")
    op.drop_table("connector_sources")

    op.drop_index("idx_connector_accounts_user_provider", table_name="connector_accounts")
    op.drop_table("connector_accounts")

    op.drop_index(
        "idx_connector_provider_configs_provider",
        table_name="connector_provider_configs",
    )
    op.drop_table("connector_provider_configs")
