"""drop dead connector source columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("idx_connector_sources_tenant_id", table_name="connector_sources")
    op.drop_column("connector_sources", "root_mime_type")


def downgrade() -> None:
    op.add_column(
        "connector_sources",
        sa.Column("root_mime_type", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "idx_connector_sources_tenant_id",
        "connector_sources",
        ["tenant_id"],
        unique=False,
    )
