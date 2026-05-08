"""connector provider core

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_CONSTRAINTS = (
    ("connector_provider_configs", "connector_provider_configs_provider_check"),
    ("connector_accounts", "connector_accounts_provider_check"),
    ("connector_sources", "connector_sources_provider_check"),
    ("connector_sync_jobs", "connector_sync_jobs_provider_check"),
)


def upgrade() -> None:
    for table, constraint in TABLE_CONSTRAINTS:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(constraint, table, "provider <> ''")


def downgrade() -> None:
    for table, constraint in TABLE_CONSTRAINTS:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(constraint, table, "provider IN ('google_drive')")
