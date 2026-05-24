"""remove document webhook events

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM webhook_deliveries
            WHERE event = ANY(
                ARRAY[
                    'document.processing',
                    'document.ready',
                    'document.failed',
                    'document.deleted'
                ]::text[]
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE webhooks
            SET events = array_remove(
                array_remove(
                    array_remove(
                        array_remove(events, 'document.processing'),
                        'document.ready'
                    ),
                    'document.failed'
                ),
                'document.deleted'
            )
            WHERE events && ARRAY[
                'document.processing',
                'document.ready',
                'document.failed',
                'document.deleted'
            ]::text[]
            """
        )
    )
    op.execute(sa.text("DELETE FROM webhooks WHERE cardinality(events) = 0"))


def downgrade() -> None:
    pass
