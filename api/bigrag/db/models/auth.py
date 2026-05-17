from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bigrag.db.base import TS, Base, TSupd, UUIDpk


class User(Base):
    __tablename__ = "users"
    __table_args__ = (sa.Index("idx_users_created_at_id", "created_at", "id"),)

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


class UserSession(Base):
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


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        sa.Index("idx_api_keys_user_id", "user_id"),
        sa.Index("idx_api_keys_expires_at", "expires_at"),
        sa.Index("idx_api_keys_active", "active"),
        sa.Index("idx_api_keys_prefix", "prefix"),
        sa.Index("idx_api_keys_created_at_id", sa.desc("created_at"), sa.desc("id")),
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
