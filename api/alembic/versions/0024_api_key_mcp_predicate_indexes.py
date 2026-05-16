"""add api key mcp predicate indexes

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX idx_api_keys_regular_created_at "
        "ON api_keys (created_at DESC) WHERE NOT (permissions ? 'mcp')"
    )
    op.execute(
        "CREATE INDEX idx_api_keys_mcp_user_created_at "
        "ON api_keys (user_id, created_at DESC) WHERE permissions ? 'mcp'"
    )
    op.execute(
        "CREATE INDEX idx_api_keys_mcp_server_name "
        "ON api_keys ((permissions->'mcp'->>'server_name')) WHERE permissions ? 'mcp'"
    )


def downgrade() -> None:
    op.drop_index("idx_api_keys_mcp_server_name", table_name="api_keys")
    op.drop_index("idx_api_keys_mcp_user_created_at", table_name="api_keys")
    op.drop_index("idx_api_keys_regular_created_at", table_name="api_keys")
