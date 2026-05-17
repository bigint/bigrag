## Alembic Consolidation Plan

### Inventory (30 migrations)
- 0001 initial schema — 495-line hand-written baseline mirroring bigrag.db.models
- 0002 data backfill — recount collections.document_count
- 0003 check-constraint widen — embedding_presets.provider adds 'voyage'
- 0004 DROP collections.redact_pii and collections.moderation_enabled
- 0005 add query_log.collection_id UUID + FK CASCADE + index + backfill
- 0006 default change — collections.index_type → HNSW, normalize existing rows
- 0007 add access_log table + 7 indexes
- 0008 DROP api_keys.rate_limits JSONB
- 0009 DROP s3_ingest_jobs table
- 0010 add chat_conversations + chat_messages (later dropped 0023)
- 0011 DATA cleanup — strip playground from user_preferences.data
- 0012 add collections.embedding_preset_id FK RESTRICT + backfill
- 0013 add google-drive connector tables (5 tables)
- 0014 add instance_settings (key/JSONB/EncryptedString)
- 0015 add upload_sessions + upload_session_items
- 0016 add maintenance_locks + backup_jobs (readable backups)
- 0017 connector provider check IN ('google_drive') → provider <> ''
- 0018 PG RULES no_audit_update, no_audit_delete on audit_log (later replaced)
- 0019 embedding_presets adds openai_compatible
- 0020 DATA cleanup — DELETE 6 obsolete instance_settings keys
- 0021 add collections.vector_store_provider + check + backfill
- 0022 5 composite indexes for admin list views
- 0023 DROP chat_messages + chat_conversations
- 0024 3 partial expression indexes on api_keys for MCP predicates
- 0025 DATA cleanup — strip chat.question_suggestions from user_preferences
- 0026 add chat_question_suggestions table (collection_id PK)
- 0027 REPLACES 0018 RULES with audit_log_block_content_modifications() + audit_log_block_delete() plpgsql + triggers
- 0028 4 (created_at DESC, id DESC) composite keyset-pagination indexes
- 0029 8 composite/partial pagination + webhook polling indexes
- 0030 drops server_default=gen_random_uuid() on id of 19 tables (client uuid7)

### Drops to preserve (do NOT recreate)
- collections.redact_pii, collections.moderation_enabled → 0004
- api_keys.rate_limits (JSONB) → 0008
- table s3_ingest_jobs → 0009
- tables chat_conversations, chat_messages → 0023 (only chat_question_suggestions from 0026 stays)
- Legacy RULES no_audit_update/no_audit_delete on audit_log → 0027 supersedes 0018
- Old id server_default gen_random_uuid() on 19 tables → 0030 removed it; consolidated migration must NOT emit server_default on those ids

### Bootstrap / reference impact
- api/bigrag/db/bootstrap.py — just runs command.upgrade(cfg, "head"). No revision IDs hardcoded.
- api/alembic/env.py — uses Base.metadata, no IDs.
- api/bigrag/services/backup/jobs.py:183 — reads SELECT version_num FROM alembic_version, stores in manifest as db_revision. Informational; will become "0001".
- api/Dockerfile, api/pyproject.toml — no version pinning.
- Tests, e2e/, dev.sh, docker-compose, docs — none reference revision IDs.

Conclusion: safe.

### Consolidation recipe
1. `rm api/alembic/versions/00{01..30}_*.py` (delete all 30)
2. `dropdb bigrag_dev && createdb bigrag_dev`
3. `cd api && uv run alembic revision --autogenerate -m "initial schema"`
4. Rename to `0001_initial_schema.py`, force revision="0001", down_revision=None
5. Manually append the audit_log triggers from 0027 to end of upgrade() after audit_log created
6. Drop all data migrations (0002, 0011, 0020, 0025) — pre-release ⇒ no data
7. Verify (see below)

bootstrap.py requires zero changes.

### Raw-SQL DDL that won't autogenerate
Audit_log immutability triggers from 0027. Append to upgrade() after audit_log:
```python
op.execute("""CREATE OR REPLACE FUNCTION audit_log_block_content_modifications()
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
$$ LANGUAGE plpgsql;""")
op.execute("""CREATE OR REPLACE FUNCTION audit_log_block_delete()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log rows cannot be deleted';
END;
$$ LANGUAGE plpgsql;""")
op.execute("DROP TRIGGER IF EXISTS audit_log_no_content_update ON audit_log;")
op.execute("CREATE TRIGGER audit_log_no_content_update BEFORE UPDATE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_block_content_modifications();")
op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;")
op.execute("CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_block_delete();")
```
Do NOT port 0018's RULES (buggy, replaced).

uuidv7: nothing extra to port. No Postgres function — generation Python-side (bigrag/ids.py:uuid7, UUIDpk in db/base.py with default=uuid7).

### Verification commands
```bash
dropdb --if-exists bigrag_dev && createdb bigrag_dev
cd api && uv run alembic upgrade head
uv run alembic history          # → one row: 0001 (head)
uv run alembic current          # → 0001 (head)
# Drift check — autogenerate must produce empty diff:
uv run alembic revision --autogenerate -m drift_check
# Inspect generated upgrade()/downgrade() — both should be only `pass`. Then:
rm api/alembic/versions/*_drift_check.py
# Round trip + sanity:
dropdb bigrag_dev && createdb bigrag_dev
cd api && uv run alembic upgrade head
psql bigrag_dev -c "\dt"
psql bigrag_dev -c "\d audit_log"
psql bigrag_dev -c "\df audit_log_block*"
psql bigrag_dev -c "\d users"
psql bigrag_dev -c "SELECT version_num FROM alembic_version;"
cd api && uv run python -c "import asyncio; from bigrag.db.bootstrap import run_migrations; asyncio.run(run_migrations())"
cd api && uv run pytest
```

### Risks
- Trigger name collision on re-apply — use DROP TRIGGER IF EXISTS prefix (already shown).
- gen_random_uuid() / pgcrypto extension — only old (deleted) migrations referenced it; no longer needed for DDL.
- env.py default schema public; raw SQL triggers assume public — don't change schema without updating both.
- Existing dev/CI databases still holding alembic_version='0030' will refuse to upgrade. Mitigation: dropdb+createdb or DELETE FROM alembic_version + alembic stamp 0001.
- Backup manifests previously had db_revision="0030"; new backups → "0001". Informational only.
- Autogenerate quirks to eyeball: literal_column emission for Index expressions, CHECK constraint names (users_role_check, collections_vector_store_provider_check, embedding_presets_provider_check, chat_question_suggestions_questions_array_check), JSONB server_default formatting.
