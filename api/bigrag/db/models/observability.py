from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk


class BackupJob(Base):
    __tablename__ = "backup_jobs"
    __table_args__ = (
        sa.Index("idx_backup_jobs_created_at", "created_at"),
        sa.Index("idx_backup_jobs_status", "status"),
        sa.Index("idx_backup_jobs_created_at_id", sa.desc("created_at"), sa.desc("id")),
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
        sa.Index("idx_access_log_actor_created_at", "actor_id", sa.desc("created_at")),
        sa.Index("idx_access_log_api_key_id", "api_key_id"),
        sa.Index("idx_access_log_action", "action"),
        sa.Index("idx_access_log_action_created_at", "action", sa.desc("created_at")),
        sa.Index("idx_access_log_collection", "collection_name"),
        sa.Index(
            "idx_access_log_collection_created_at",
            "collection_name",
            sa.desc("created_at"),
        ),
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
