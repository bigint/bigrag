from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk
from bigrag.services.crypto import EncryptedString


class ConnectorSource(Base):
    __tablename__ = "connector_sources"
    __table_args__ = (
        sa.Index("idx_connector_sources_collection_id", "collection_id"),
        sa.Index("idx_connector_sources_next_sync", "next_sync_at"),
        sa.Index("idx_connector_sources_tenant_id", "tenant_id"),
        sa.UniqueConstraint(
            "provider",
            "collection_id",
            "root_id",
            name="uq_connector_sources_provider_collection_root",
        ),
        sa.CheckConstraint(
            "provider <> ''",
            name="connector_sources_provider_check",
        ),
        sa.CheckConstraint(
            "source_type IN ('prefix')",
            name="connector_sources_source_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('idle', 'syncing', 'error')",
            name="connector_sources_status_check",
        ),
    )

    id: Mapped[UUIDpk]
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
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


class ConnectorSourceCredential(Base):
    __tablename__ = "connector_source_credentials"
    __table_args__ = (sa.Index("idx_connector_source_credentials_source_id", "source_id"),)

    id: Mapped[UUIDpk]
    source_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("connector_sources.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    access_key_id: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    secret_access_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    session_token: Mapped[str | None] = mapped_column(EncryptedString)
    region: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="us-east-1")
    endpoint_url: Mapped[str | None] = mapped_column(sa.Text)
    force_path_style: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
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
            "provider <> ''",
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
