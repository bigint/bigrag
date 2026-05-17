from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd
from bigrag.services.crypto import EncryptedString


class InstanceSetting(Base):
    __tablename__ = "instance_settings"

    key: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    secret_value: Mapped[str | None] = mapped_column(EncryptedString)
    updated_by: Mapped[UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
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
