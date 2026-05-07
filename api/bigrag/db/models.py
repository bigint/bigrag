from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk
from bigrag.services.crypto import EncryptedString


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUIDpk]
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    role: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint("role IN ('admin', 'member')", name="users_role_check"),
        nullable=False,
        server_default="member",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        sa.Index("idx_sessions_user_id", "user_id"),
        sa.Index("idx_sessions_expires_at", "expires_at"),
    )

    id: Mapped[UUIDpk]
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[TS]


class InstanceSetting(Base):
    __tablename__ = "instance_settings"

    key: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    secret_value: Mapped[str | None] = mapped_column(EncryptedString)
    updated_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        sa.Index("idx_api_keys_user_id", "user_id"),
        sa.Index("idx_api_keys_expires_at", "expires_at"),
        sa.Index("idx_api_keys_active", "active"),
        sa.Index("idx_api_keys_prefix", "prefix"),
    )

    id: Mapped[UUIDpk]
    user_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(sa.Text, nullable=False)
    permissions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (sa.Index("idx_collections_name", "name"),)

    id: Mapped[UUIDpk]
    name: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    embedding_provider: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="openai"
    )
    embedding_model: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="text-embedding-3-small"
    )
    embedding_api_key: Mapped[str | None] = mapped_column(EncryptedString)
    embedding_base_url: Mapped[str | None] = mapped_column(sa.Text)
    embedding_preset_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("embedding_presets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    dimension: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("1536")
    )
    chunk_size: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("512")
    )
    chunk_overlap: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("50")
    )
    chunk_strategy: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="paragraph")
    document_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    default_top_k: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("10")
    )
    default_min_score: Mapped[float | None] = mapped_column(sa.Double)
    default_search_mode: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="semantic"
    )
    reranking_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    reranking_model: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="rerank-v3.5"
    )
    reranking_api_key: Mapped[str | None] = mapped_column(EncryptedString)
    index_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="HNSW")
    tenant_field: Mapped[str | None] = mapped_column(sa.Text)
    metadata_schema: Mapped[dict | None] = mapped_column(JSONB)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        sa.Index("idx_documents_collection_id", "collection_id"),
        sa.Index("idx_documents_status", "status"),
        sa.Index("idx_documents_created_at", "created_at"),
        sa.Index("idx_documents_collection_hash", "collection_id", "content_hash"),
    )

    id: Mapped[UUIDpk]
    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    file_size: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    file_path: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    chunk_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    token_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    content_hash: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="documents_status_check",
        ),
        nullable=False,
        server_default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class UploadSession(Base):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        sa.Index("idx_upload_sessions_collection_created", "collection_id", "created_at"),
        sa.Index("idx_upload_sessions_status", "status"),
        sa.CheckConstraint(
            "status IN ('preparing', 'uploading', 'ingesting', 'complete', 'failed', 'canceled')",
            name="upload_sessions_status_check",
        ),
    )

    id: Mapped[UUIDpk]
    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="preparing")
    total_files: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_bytes: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    uploaded_files: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    queued_files: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    completed_files: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    failed_files: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    canceled_files: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    created_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class UploadSessionItem(Base):
    __tablename__ = "upload_session_items"
    __table_args__ = (
        sa.Index("idx_upload_session_items_session", "session_id"),
        sa.Index("idx_upload_session_items_document", "document_id"),
        sa.Index("idx_upload_session_items_status", "status"),
        sa.UniqueConstraint("session_id", "client_item_id", name="uq_upload_items_session_client"),
        sa.CheckConstraint(
            "status IN ('queued', 'complete', 'failed', 'canceled')",
            name="upload_session_items_status_check",
        ),
    )

    id: Mapped[UUIDpk]
    session_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False
    )
    client_item_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("documents.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    file_size: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    content_hash: Mapped[str | None] = mapped_column(sa.Text)
    storage_key: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="queued")
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class MaintenanceLock(Base):
    __tablename__ = "maintenance_locks"
    __table_args__ = (sa.Index("idx_maintenance_locks_expires_at", "expires_at"),)

    name: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    owner_id: Mapped[UUID | None] = mapped_column(sa.Uuid)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class BackupJob(Base):
    __tablename__ = "backup_jobs"
    __table_args__ = (
        sa.Index("idx_backup_jobs_created_at", "created_at"),
        sa.Index("idx_backup_jobs_status", "status"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="backup_jobs_status_check",
        ),
    )

    id: Mapped[UUIDpk]
    label: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="pending")
    progress: Mapped[float] = mapped_column(sa.Double, nullable=False, server_default=sa.text("0"))
    destination_prefix: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    object_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    byte_count: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False, server_default=sa.text("0")
    )
    manifest: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    created_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ConnectorProviderConfig(Base):
    __tablename__ = "connector_provider_configs"
    __table_args__ = (
        sa.Index("idx_connector_provider_configs_provider", "provider"),
        sa.CheckConstraint(
            "provider IN ('google_drive')",
            name="connector_provider_configs_provider_check",
        ),
    )

    id: Mapped[UUIDpk]
    provider: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    client_id: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    client_secret: Mapped[str | None] = mapped_column(EncryptedString)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ConnectorAccount(Base):
    __tablename__ = "connector_accounts"
    __table_args__ = (
        sa.Index("idx_connector_accounts_user_provider", "user_id", "provider"),
        sa.UniqueConstraint("user_id", "provider", name="uq_connector_accounts_user_provider"),
        sa.CheckConstraint(
            "provider IN ('google_drive')",
            name="connector_accounts_provider_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'connected', 'needs_reauth', 'revoked')",
            name="connector_accounts_status_check",
        ),
    )

    id: Mapped[UUIDpk]
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_email: Mapped[str | None] = mapped_column(sa.Text)
    access_token: Mapped[str | None] = mapped_column(EncryptedString)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString)
    token_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="pending")
    oauth_state: Mapped[str | None] = mapped_column(sa.Text)
    last_connected_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ConnectorSource(Base):
    __tablename__ = "connector_sources"
    __table_args__ = (
        sa.Index("idx_connector_sources_account_id", "account_id"),
        sa.Index("idx_connector_sources_collection_id", "collection_id"),
        sa.Index("idx_connector_sources_next_sync", "next_sync_at"),
        sa.UniqueConstraint(
            "account_id",
            "collection_id",
            "root_id",
            name="uq_connector_sources_account_collection_root",
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
    )

    id: Mapped[UUIDpk]
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("connector_accounts.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    root_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    root_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    root_mime_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="idle")
    schedule_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    sync_interval_hours: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("24")
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(sa.Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ConnectorDocument(Base):
    __tablename__ = "connector_documents"
    __table_args__ = (
        sa.Index("idx_connector_documents_document_id", "document_id"),
        sa.Index("idx_connector_documents_source_remote", "source_id", "remote_id"),
        sa.UniqueConstraint(
            "source_id",
            "remote_id",
            name="uq_connector_documents_source_remote",
        ),
    )

    id: Mapped[UUIDpk]
    source_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("connector_sources.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    remote_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    remote_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    remote_mime_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    remote_checksum: Mapped[str | None] = mapped_column(sa.Text)
    remote_version: Mapped[str | None] = mapped_column(sa.Text)
    remote_modified_time: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(sa.Text)
    web_url: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="active")
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ConnectorSyncJob(Base):
    __tablename__ = "connector_sync_jobs"
    __table_args__ = (
        sa.Index("idx_connector_sync_jobs_source_created", "source_id", "created_at"),
        sa.Index("idx_connector_sync_jobs_status", "status"),
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
    )

    id: Mapped[UUIDpk]
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("connector_sources.id", ondelete="SET NULL")
    )
    trigger: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="pending")
    started_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    total_found: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_created: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_updated: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_skipped: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_deleted: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_failed: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Webhook(Base):
    __tablename__ = "webhooks"
    __table_args__ = (sa.Index("idx_webhooks_created_by", "created_by"),)

    id: Mapped[UUIDpk]
    url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    secret: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(sa.Text), nullable=False)
    collections: Mapped[list[str] | None] = mapped_column(ARRAY(sa.Text))
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        sa.Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
        sa.Index("idx_webhook_deliveries_status", "status"),
    )

    id: Mapped[UUIDpk]
    webhook_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="webhook_deliveries_status_check",
        ),
        nullable=False,
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    last_status_code: Mapped[int | None] = mapped_column(sa.Integer)
    last_error: Mapped[str | None] = mapped_column(sa.Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class QueryLog(Base):
    __tablename__ = "query_log"
    __table_args__ = (
        sa.Index("idx_query_log_collection", "collection_name"),
        sa.Index("idx_query_log_collection_id", "collection_id"),
        sa.Index("idx_query_log_created_at", "created_at"),
    )

    id: Mapped[UUIDpk]
    collection_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE")
    )
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    query: Mapped[str] = mapped_column(sa.Text, nullable=False)
    top_k: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    result_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    avg_score: Mapped[float | None] = mapped_column(sa.Double)
    latency_ms: Mapped[float | None] = mapped_column(sa.Double)
    search_mode: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="semantic")
    created_at: Mapped[TS]


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        sa.Index("idx_chat_conversations_owner_updated", "owner_id", "updated_at"),
        sa.Index("idx_chat_conversations_collection", "collection_name"),
    )

    id: Mapped[UUIDpk]
    owner_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="New chat")
    collection_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="SET NULL")
    )
    collection_name: Mapped[str | None] = mapped_column(sa.Text)
    model_provider: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="openai")
    model: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="gpt-4o-mini")
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    default_top_k: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("5")
    )
    default_search_mode: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="semantic"
    )
    default_min_score: Mapped[float | None] = mapped_column(sa.Double)
    default_rerank: Mapped[bool | None] = mapped_column(sa.Boolean)
    temperature: Mapped[float] = mapped_column(
        sa.Double, nullable=False, server_default=sa.text("0.2")
    )
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        sa.Index("idx_chat_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[UUIDpk]
    conversation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="chat_messages_role_check",
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model_provider: Mapped[str | None] = mapped_column(sa.Text)
    model: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "status IN ('complete', 'error')",
            name="chat_messages_status_check",
        ),
        nullable=False,
        server_default="complete",
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    retrieval: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]


class EmbeddingPreset(Base):
    __tablename__ = "embedding_presets"
    __table_args__ = (sa.Index("idx_embedding_presets_name", "name"),)

    id: Mapped[UUIDpk]
    name: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "provider IN ('openai', 'cohere', 'voyage')",
            name="embedding_presets_provider_check",
        ),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    api_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    base_url: Mapped[str | None] = mapped_column(sa.Text)
    dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    updated_at: Mapped[TSupd]


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        sa.Index("idx_audit_actor", "actor_id"),
        sa.Index("idx_audit_api_key_id", "api_key_id"),
        sa.Index("idx_audit_action", "action"),
        sa.Index("idx_audit_created_at", sa.desc("created_at")),
    )

    id: Mapped[UUIDpk]
    actor_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(sa.Text)
    api_key_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("api_keys.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(sa.Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    ip: Mapped[str | None] = mapped_column(sa.Text)
    user_agent: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[TS]


class AccessLog(Base):
    __tablename__ = "access_log"
    __table_args__ = (
        sa.Index("idx_access_log_actor", "actor_id"),
        sa.Index("idx_access_log_api_key_id", "api_key_id"),
        sa.Index("idx_access_log_action", "action"),
        sa.Index("idx_access_log_collection", "collection_name"),
        sa.Index("idx_access_log_created_at", sa.desc("created_at")),
        sa.Index("idx_access_log_status", "status_code"),
        sa.Index("idx_access_log_success", "success"),
    )

    id: Mapped[UUIDpk]
    actor_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(sa.Text)
    api_key_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("api_keys.id", ondelete="SET NULL")
    )
    api_key_name: Mapped[str | None] = mapped_column(sa.Text)
    auth_method: Mapped[str | None] = mapped_column(sa.Text)
    action: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="http.request")
    resource_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="http")
    resource_id: Mapped[str | None] = mapped_column(sa.Text)
    collection_name: Mapped[str | None] = mapped_column(sa.Text)
    method: Mapped[str] = mapped_column(sa.Text, nullable=False)
    path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    route: Mapped[str | None] = mapped_column(sa.Text)
    status_code: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    success: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    latency_ms: Mapped[float] = mapped_column(sa.Double, nullable=False)
    request_id: Mapped[str | None] = mapped_column(sa.Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    ip: Mapped[str | None] = mapped_column(sa.Text)
    user_agent: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[TS]


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    __table_args__ = (sa.Index("idx_embedding_cache_last_hit", "last_hit_at"),)

    content_hash: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    model_key: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    vector: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[TS]
    last_hit_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )
