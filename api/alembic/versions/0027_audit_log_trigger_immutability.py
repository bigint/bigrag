"""replace audit_log RULE-based immutability with selective TRIGGER

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-16

The previous ``DO INSTEAD NOTHING`` rules silently broke referential
integrity enforcement on tables referenced by audit_log (e.g., api_keys,
users). When deleting a row from those tables, Postgres tried to apply the
FK's ``ON DELETE SET NULL`` action — which is an UPDATE on audit_log —
and the rule rewrote it to nothing, raising ``referential integrity query
on "X" from constraint ... gave unexpected result``.

The trigger replacement only blocks UPDATEs that change *audit content*
(action, resource_type, resource_id, metadata, created_at). It explicitly
allows FK-driven SET NULL updates on actor_id and api_key_id. DELETE is
fully blocked.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP RULE IF EXISTS no_audit_delete ON audit_log")
    op.execute("DROP RULE IF EXISTS no_audit_update ON audit_log")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_block_content_modifications()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.action IS DISTINCT FROM NEW.action
               OR OLD.resource_type IS DISTINCT FROM NEW.resource_type
               OR OLD.resource_id IS DISTINCT FROM NEW.resource_id
               OR OLD.metadata IS DISTINCT FROM NEW.metadata
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.actor_email IS DISTINCT FROM NEW.actor_email
               OR OLD.ip IS DISTINCT FROM NEW.ip
               OR OLD.user_agent IS DISTINCT FROM NEW.user_agent THEN
                RAISE EXCEPTION 'audit_log content is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_block_delete()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log rows cannot be deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_content_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_block_content_modifications();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_block_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_content_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_block_delete()")
    op.execute("DROP FUNCTION IF EXISTS audit_log_block_content_modifications()")
    op.execute("CREATE RULE no_audit_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING")
    op.execute("CREATE RULE no_audit_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING")
