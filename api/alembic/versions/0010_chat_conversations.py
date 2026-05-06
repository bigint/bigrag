"""add chat conversations

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), server_default="New chat", nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=True),
        sa.Column("collection_name", sa.Text(), nullable=True),
        sa.Column("model_provider", sa.Text(), server_default="openai", nullable=False),
        sa.Column("model", sa.Text(), server_default="gpt-4o-mini", nullable=False),
        sa.Column("system_prompt", sa.Text(), server_default="", nullable=False),
        sa.Column("default_top_k", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("default_search_mode", sa.Text(), server_default="semantic", nullable=False),
        sa.Column("default_min_score", sa.Double(), nullable=True),
        sa.Column("default_rerank", sa.Boolean(), nullable=True),
        sa.Column("temperature", sa.Double(), server_default=sa.text("0.2"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_conversations_owner_updated",
        "chat_conversations",
        ["owner_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_chat_conversations_collection",
        "chat_conversations",
        ["collection_name"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="complete", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "retrieval",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="chat_messages_role_check",
        ),
        sa.CheckConstraint(
            "status IN ('complete', 'error')",
            name="chat_messages_status_check",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_messages_conversation_created",
        "chat_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_chat_messages_conversation_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("idx_chat_conversations_collection", table_name="chat_conversations")
    op.drop_index("idx_chat_conversations_owner_updated", table_name="chat_conversations")
    op.drop_table("chat_conversations")
