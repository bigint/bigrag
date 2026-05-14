"""allow openai_compatible embedding presets

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("embedding_presets_provider_check", "embedding_presets", type_="check")
    op.create_check_constraint(
        "embedding_presets_provider_check",
        "embedding_presets",
        "provider IN ('openai', 'openai_compatible', 'cohere', 'voyage')",
    )


def downgrade() -> None:
    op.drop_constraint("embedding_presets_provider_check", "embedding_presets", type_="check")
    op.create_check_constraint(
        "embedding_presets_provider_check",
        "embedding_presets",
        "provider IN ('openai', 'cohere', 'voyage')",
    )
