"""audit log immutability rules

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE RULE no_audit_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING")
    op.execute("CREATE RULE no_audit_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING")


def downgrade() -> None:
    op.execute("DROP RULE IF EXISTS no_audit_delete ON audit_log")
    op.execute("DROP RULE IF EXISTS no_audit_update ON audit_log")
