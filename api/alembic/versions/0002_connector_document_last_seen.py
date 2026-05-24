"""connector document last seen job

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "connector_documents",
        sa.Column("last_seen_job_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "idx_connector_documents_source_last_seen",
        "connector_documents",
        ["source_id", "last_seen_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_connector_documents_source_last_seen",
        table_name="connector_documents",
    )
    op.drop_column("connector_documents", "last_seen_job_id")
