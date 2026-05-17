"""use client generated uuidv7 ids

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_TABLES = (
    "users",
    "sessions",
    "api_keys",
    "collections",
    "documents",
    "upload_sessions",
    "upload_session_items",
    "backup_jobs",
    "connector_provider_configs",
    "connector_accounts",
    "connector_sources",
    "connector_documents",
    "connector_sync_jobs",
    "webhooks",
    "webhook_deliveries",
    "query_log",
    "embedding_presets",
    "audit_log",
    "access_log",
)


def upgrade() -> None:
    for table in ID_TABLES:
        op.alter_column(table, "id", existing_type=sa.Uuid(), server_default=None)


def downgrade() -> None:
    for table in ID_TABLES:
        op.alter_column(
            table,
            "id",
            existing_type=sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
        )
