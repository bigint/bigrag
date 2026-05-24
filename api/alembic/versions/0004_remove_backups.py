"""remove backups

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM instance_settings
            WHERE key = ANY(
                ARRAY[
                    'backup_s3_access_key_id',
                    'backup_s3_bucket',
                    'backup_s3_endpoint_url',
                    'backup_s3_force_path_style',
                    'backup_s3_prefix',
                    'backup_s3_region',
                    'backup_s3_secret_access_key'
                ]::text[]
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM webhook_deliveries
            WHERE event = ANY(
                ARRAY['backup.started', 'backup.succeeded', 'backup.failed']::text[]
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
                    array_remove(events, 'backup.started'),
                    'backup.succeeded'
                ),
                'backup.failed'
            )
            WHERE events && ARRAY['backup.started', 'backup.succeeded', 'backup.failed']::text[]
            """
        )
    )
    op.execute(sa.text("DELETE FROM webhooks WHERE cardinality(events) = 0"))
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
    op.execute(
        sa.text(
            """
            DELETE FROM audit_log
            WHERE action LIKE 'backup.%'
                OR resource_type = 'backup_job'
            """
        )
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_block_delete();
        """
    )
    op.execute(
        sa.text(
            """
            DELETE FROM access_log
            WHERE path = '/v1/admin/backups'
                OR path LIKE '/v1/admin/backups/%'
                OR route = '/v1/admin/backups'
                OR route LIKE '/v1/admin/backups/%'
            """
        )
    )
    op.execute(sa.text("DROP TABLE IF EXISTS backup_jobs CASCADE"))


def downgrade() -> None:
    op.create_table(
        "backup_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("progress", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column("destination_prefix", sa.Text(), server_default="", nullable=False),
        sa.Column("object_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("byte_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="backup_jobs_status_check",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_backup_jobs_created_at", "backup_jobs", ["created_at"], unique=False)
    op.create_index(
        "idx_backup_jobs_created_at_id",
        "backup_jobs",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index("idx_backup_jobs_status", "backup_jobs", ["status"], unique=False)
