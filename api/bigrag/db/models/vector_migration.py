from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk


class VectorMigrationJob(Base):
    __tablename__ = "vector_migration_jobs"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="vector_migration_jobs_status_check",
        ),
        sa.Index("idx_vector_migration_jobs_collection", "collection_name"),
        sa.Index("idx_vector_migration_jobs_status", "status"),
        sa.Index(
            "idx_vector_migration_jobs_created_at_id",
            sa.desc("created_at"),
            sa.desc("id"),
        ),
    )

    id: Mapped[UUIDpk]
    collection_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="SET NULL")
    )
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    target_provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="pending")
    phase: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="queued")
    progress: Mapped[float] = mapped_column(sa.Double, nullable=False, server_default=sa.text("0"))
    copied_points: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_points: Mapped[int | None] = mapped_column(sa.Integer)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    created_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]
