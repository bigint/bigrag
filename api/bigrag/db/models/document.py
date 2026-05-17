from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        sa.Index("idx_documents_collection_id", "collection_id"),
        sa.Index("idx_documents_status", "status"),
        sa.Index("idx_documents_created_at", "created_at"),
        sa.Index("idx_documents_collection_created_at", "collection_id", sa.desc("created_at")),
        sa.Index(
            "idx_documents_collection_status_created_at",
            "collection_id",
            "status",
            sa.desc("created_at"),
        ),
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


class ChatQuestionSuggestion(Base):
    __tablename__ = "chat_question_suggestions"

    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    questions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    model: Mapped[str | None] = mapped_column(sa.Text)
    generated_by: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    generated_at: Mapped[TS]
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
