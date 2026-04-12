"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-12

Fresh baseline. Creates the full metadata schema via
``Base.metadata.create_all`` so the initial snapshot tracks
``bigrag.db.models`` byte-for-byte — including ``EncryptedString`` columns.
Subsequent revisions use conventional ``op.create_table`` / ``op.alter_column``
ops.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from bigrag.db import models  # noqa: F401  — register tables
from bigrag.db.base import Base

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
