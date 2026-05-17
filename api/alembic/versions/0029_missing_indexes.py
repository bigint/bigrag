"""add missing composite/partial indexes for pagination and webhook polling

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_collections_created_at_id",
        "collections",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "idx_users_created_at_id",
        "users",
        [sa.literal_column("created_at ASC"), sa.literal_column("id ASC")],
        unique=False,
    )
    op.create_index(
        "idx_api_keys_created_at_id",
        "api_keys",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "idx_webhooks_created_at_id",
        "webhooks",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "idx_backup_jobs_created_at_id",
        "backup_jobs",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "idx_webhooks_active",
        "webhooks",
        ["active"],
        unique=False,
    )
    op.create_index(
        "idx_webhook_deliveries_pending_retry",
        "webhook_deliveries",
        ["status", "next_retry_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_connector_accounts_oauth_state",
        "connector_accounts",
        ["oauth_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_connector_accounts_oauth_state", table_name="connector_accounts")
    op.drop_index("idx_webhook_deliveries_pending_retry", table_name="webhook_deliveries")
    op.drop_index("idx_webhooks_active", table_name="webhooks")
    op.drop_index("idx_backup_jobs_created_at_id", table_name="backup_jobs")
    op.drop_index("idx_webhooks_created_at_id", table_name="webhooks")
    op.drop_index("idx_api_keys_created_at_id", table_name="api_keys")
    op.drop_index("idx_users_created_at_id", table_name="users")
    op.drop_index("idx_collections_created_at_id", table_name="collections")
