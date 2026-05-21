from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk
from bigrag.services.crypto import EncryptedString


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        sa.Index("idx_collections_name", "name"),
        sa.Index("idx_collections_created_at_id", sa.desc("created_at"), sa.desc("id")),
    )

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
    multimodal_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    multimodal_enrichment_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    tenant_field: Mapped[str | None] = mapped_column(sa.Text)
    metadata_schema: Mapped[dict | None] = mapped_column(JSONB)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class EmbeddingPreset(Base):
    __tablename__ = "embedding_presets"
    __table_args__ = (
        sa.CheckConstraint(
            "provider IN ('openai', 'openai_compatible', 'cohere', 'voyage')",
            name="embedding_presets_provider_check",
        ),
        sa.Index("idx_embedding_presets_name", "name"),
    )

    id: Mapped[UUIDpk]
    name: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    api_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    base_url: Mapped[str | None] = mapped_column(sa.Text)
    dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


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
