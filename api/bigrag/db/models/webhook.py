from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk
from bigrag.services.crypto import EncryptedString


class Webhook(Base):
    __tablename__ = "webhooks"
    __table_args__ = (
        sa.Index("idx_webhooks_created_by", "created_by"),
        sa.Index("idx_webhooks_active", "active"),
        sa.Index("idx_webhooks_created_at_id", sa.desc("created_at"), sa.desc("id")),
    )

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
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="webhook_deliveries_status_check",
        ),
        sa.Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
        sa.Index("idx_webhook_deliveries_status", "status"),
        sa.Index(
            "idx_webhook_deliveries_pending_retry",
            "status",
            "next_retry_at",
            "created_at",
        ),
    )

    id: Mapped[UUIDpk]
    webhook_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    last_status_code: Mapped[int | None] = mapped_column(sa.Integer)
    last_error: Mapped[str | None] = mapped_column(sa.Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
