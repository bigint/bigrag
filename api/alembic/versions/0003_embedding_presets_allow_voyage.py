"""allow voyage in embedding_presets.provider check

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26

The Pydantic schema and embedding service support ``voyage`` as a
provider, but the original CHECK constraint on ``embedding_presets``
only listed ``('openai', 'cohere')``. Inserting a Voyage preset
therefore failed with a constraint violation. Widen the check.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("embedding_presets_provider_check", "embedding_presets", type_="check")
    op.create_check_constraint(
        "embedding_presets_provider_check",
        "embedding_presets",
        "provider IN ('openai', 'cohere', 'voyage')",
    )


def downgrade() -> None:
    op.drop_constraint("embedding_presets_provider_check", "embedding_presets", type_="check")
    op.create_check_constraint(
        "embedding_presets_provider_check",
        "embedding_presets",
        "provider IN ('openai', 'cohere')",
    )
