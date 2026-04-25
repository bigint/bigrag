"""recount Collection.document_count to include all statuses

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25

Backfill for the change in semantics: ``Collection.document_count`` now
reflects every document in the collection (any status) instead of only
``ready`` rows. Existing instances may have stale counters where some
documents are in ``pending`` / ``processing`` / ``failed`` and were
therefore excluded from the previous denormalized counter.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE collections c
        SET document_count = sub.cnt
        FROM (
            SELECT collection_id, COUNT(*) AS cnt
            FROM documents
            GROUP BY collection_id
        ) sub
        WHERE c.id = sub.collection_id
        """
    )
    op.execute(
        """
        UPDATE collections
        SET document_count = 0
        WHERE id NOT IN (SELECT DISTINCT collection_id FROM documents)
        """
    )


def downgrade() -> None:
    # Restore the previous "ready-only" semantics.
    op.execute(
        """
        UPDATE collections c
        SET document_count = COALESCE(sub.cnt, 0)
        FROM (
            SELECT collection_id, COUNT(*) AS cnt
            FROM documents
            WHERE status = 'ready'
            GROUP BY collection_id
        ) sub
        WHERE c.id = sub.collection_id
        """
    )
