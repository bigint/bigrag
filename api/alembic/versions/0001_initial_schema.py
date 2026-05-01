"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-12

Explicit baseline. Mirrors ``bigrag.db.models`` table-by-table so that future
``alembic revision --autogenerate`` runs see no pending diff against an empty
database.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from bigrag.services.crypto import EncryptedString

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), server_default="", nullable=False),
        sa.Column("role", sa.Text(), server_default="member", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("role IN ('admin', 'member')", name="users_role_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "sessions",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("idx_sessions_expires_at", "sessions", ["expires_at"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "rate_limits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("idx_api_keys_user_id", "api_keys", ["user_id"], unique=False)
    op.create_index("idx_api_keys_expires_at", "api_keys", ["expires_at"], unique=False)
    op.create_index("idx_api_keys_active", "api_keys", ["active"], unique=False)
    op.create_index("idx_api_keys_prefix", "api_keys", ["prefix"], unique=False)

    op.create_table(
        "collections",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("embedding_provider", sa.Text(), server_default="openai", nullable=False),
        sa.Column(
            "embedding_model",
            sa.Text(),
            server_default="text-embedding-3-small",
            nullable=False,
        ),
        sa.Column("embedding_api_key", EncryptedString(), nullable=True),
        sa.Column("embedding_base_url", sa.Text(), nullable=True),
        sa.Column("dimension", sa.Integer(), server_default=sa.text("1536"), nullable=False),
        sa.Column("chunk_size", sa.Integer(), server_default=sa.text("512"), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("chunk_strategy", sa.Text(), server_default="paragraph", nullable=False),
        sa.Column(
            "document_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "default_top_k",
            sa.Integer(),
            server_default=sa.text("10"),
            nullable=False,
        ),
        sa.Column("default_min_score", sa.Double(), nullable=True),
        sa.Column(
            "default_search_mode",
            sa.Text(),
            server_default="semantic",
            nullable=False,
        ),
        sa.Column(
            "reranking_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "reranking_model",
            sa.Text(),
            server_default="rerank-v3.5",
            nullable=False,
        ),
        sa.Column("reranking_api_key", EncryptedString(), nullable=True),
        sa.Column("index_type", sa.Text(), server_default="HNSW", nullable=False),
        sa.Column("tenant_field", sa.Text(), nullable=True),
        sa.Column("metadata_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("redact_pii", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "moderation_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_collections_name", "collections", ["name"], unique=False)

    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "file_size",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), server_default="", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="documents_status_check",
        ),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_documents_collection_id", "documents", ["collection_id"], unique=False)
    op.create_index("idx_documents_status", "documents", ["status"], unique=False)
    op.create_index("idx_documents_created_at", "documents", ["created_at"], unique=False)
    op.create_index(
        "idx_documents_collection_hash",
        "documents",
        ["collection_id", "content_hash"],
        unique=False,
    )

    op.create_table(
        "webhooks",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", EncryptedString(), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("collections", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_webhooks_created_by", "webhooks", ["created_by"], unique=False)

    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("webhook_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="webhook_deliveries_status_check",
        ),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_deliveries_webhook_id",
        "webhook_deliveries",
        ["webhook_id"],
        unique=False,
    )
    op.create_index("idx_webhook_deliveries_status", "webhook_deliveries", ["status"], unique=False)

    op.create_table(
        "query_log",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("collection_name", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_score", sa.Double(), nullable=True),
        sa.Column("latency_ms", sa.Double(), nullable=True),
        sa.Column("search_mode", sa.Text(), server_default="semantic", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_query_log_collection", "query_log", ["collection_name"], unique=False)
    op.create_index("idx_query_log_created_at", "query_log", ["created_at"], unique=False)

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
        sa.Column(
            "no_sign_request",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.Column(
            "total_ingested",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "total_skipped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
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

    op.create_table(
        "embedding_presets",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("api_key", EncryptedString(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("dimension", sa.Integer(), nullable=False),
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
            "provider IN ('openai', 'cohere')",
            name="embedding_presets_provider_check",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_embedding_presets_name", "embedding_presets", ["name"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.Text(), nullable=True),
        sa.Column("api_key_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_actor", "audit_log", ["actor_id"], unique=False)
    op.create_index("idx_audit_api_key_id", "audit_log", ["api_key_id"], unique=False)
    op.create_index("idx_audit_action", "audit_log", ["action"], unique=False)
    op.create_index(
        "idx_audit_created_at",
        "audit_log",
        [sa.literal_column("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "embedding_cache",
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("model_key", sa.Text(), nullable=False),
        sa.Column("vector", postgresql.BYTEA(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_hit_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("content_hash", "model_key"),
    )
    op.create_index(
        "idx_embedding_cache_last_hit", "embedding_cache", ["last_hit_at"], unique=False
    )


def downgrade() -> None:
    # Dropping the initial schema wipes every row in the database. That's
    # almost never what someone running `alembic downgrade` actually wants,
    # so refuse rather than silently nuke prod. Operators who genuinely
    # need a clean slate can drop the database directly.
    raise NotImplementedError(
        "initial schema is not downgradeable — drop the database if you really mean it"
    )
