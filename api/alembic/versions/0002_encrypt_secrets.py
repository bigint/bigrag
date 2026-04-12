"""encrypt secret columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-12

Encrypts plaintext secret columns in place with the process-level Fernet key
from ``BIGRAG_MASTER_KEY``:

- ``embedding_presets.api_key``
- ``webhooks.secret``
- ``s3_ingest_jobs.access_key``
- ``s3_ingest_jobs.secret_key``

Refuses to run if no master key is set. Rows already encrypted (Fernet tokens
start with ``gAAAA``) are skipped, so the migration is idempotent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from bigrag.config import settings
from bigrag.services import crypto

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES: tuple[tuple[str, str], ...] = (
    ("embedding_presets", "api_key"),
    ("webhooks", "secret"),
    ("s3_ingest_jobs", "access_key"),
    ("s3_ingest_jobs", "secret_key"),
)

_FERNET_PREFIX = "gAAAA"


def _ensure_key() -> None:
    if not settings.master_key:
        raise RuntimeError(
            "Migration 0002 requires BIGRAG_MASTER_KEY. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and export it before "
            "running `alembic upgrade head`."
        )
    crypto.configure(settings.master_key)


def upgrade() -> None:
    _ensure_key()
    bind = op.get_bind()
    for table, col in TABLES:
        rows = bind.execute(
            sa.text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
        ).fetchall()
        for row_id, value in rows:
            if value.startswith(_FERNET_PREFIX):
                continue
            bind.execute(
                sa.text(f"UPDATE {table} SET {col} = :v WHERE id = :id"),
                {"v": crypto.encrypt(value), "id": row_id},
            )


def downgrade() -> None:
    _ensure_key()
    bind = op.get_bind()
    for table, col in TABLES:
        rows = bind.execute(
            sa.text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
        ).fetchall()
        for row_id, value in rows:
            if not value.startswith(_FERNET_PREFIX):
                continue
            bind.execute(
                sa.text(f"UPDATE {table} SET {col} = :v WHERE id = :id"),
                {"v": crypto.decrypt(value), "id": row_id},
            )
