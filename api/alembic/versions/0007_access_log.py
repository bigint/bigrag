"""add access log stream

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_log",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.Text(), nullable=True),
        sa.Column("api_key_id", sa.Uuid(), nullable=True),
        sa.Column("api_key_name", sa.Text(), nullable=True),
        sa.Column("auth_method", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), server_default="http.request", nullable=False),
        sa.Column("resource_type", sa.Text(), server_default="http", nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("collection_name", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("route", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Double(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_access_log_actor", "access_log", ["actor_id"], unique=False)
    op.create_index("idx_access_log_api_key_id", "access_log", ["api_key_id"], unique=False)
    op.create_index("idx_access_log_action", "access_log", ["action"], unique=False)
    op.create_index("idx_access_log_collection", "access_log", ["collection_name"], unique=False)
    op.create_index(
        "idx_access_log_created_at",
        "access_log",
        [sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index("idx_access_log_status", "access_log", ["status_code"], unique=False)
    op.create_index("idx_access_log_success", "access_log", ["success"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_access_log_success", table_name="access_log")
    op.drop_index("idx_access_log_status", table_name="access_log")
    op.drop_index("idx_access_log_created_at", table_name="access_log")
    op.drop_index("idx_access_log_collection", table_name="access_log")
    op.drop_index("idx_access_log_action", table_name="access_log")
    op.drop_index("idx_access_log_api_key_id", table_name="access_log")
    op.drop_index("idx_access_log_actor", table_name="access_log")
    op.drop_table("access_log")
