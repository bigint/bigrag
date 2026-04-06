# 002: Non-Atomic Multi-System Deletes

**Status:** Open
**Severity:** Critical
**Component:** `api/bigrag/routers/documents.py`, `api/bigrag/routers/collections.py`, `api/bigrag/services/queue.py`

## Problem

Delete operations span three systems (Postgres, Milvus, file storage) with no transaction or compensation. If any step fails mid-sequence, data becomes orphaned across systems with no automatic recovery.

## Affected Operations

### Single Document Delete (`DELETE /documents/{id}`)

**File:** `routers/documents.py:233-266`

| Step | Line | System | Operation | Reversible |
|------|------|--------|-----------|------------|
| 1 | 248 | Milvus | `vector_store.delete_by_document()` | No |
| 2 | 250 | Postgres | `DELETE FROM documents WHERE id = $1` | No |
| 3 | 252-262 | Postgres | `UPDATE collections SET document_count = (...)` | Yes |
| 4 | 264 | Storage | `get_storage().delete(row["file_path"])` | No |

### Batch Document Delete (`POST /documents/batch/delete`)

**File:** `routers/documents.py:554-617`

Per document, steps 1-3 run **in parallel** via `asyncio.gather()` at lines 586-590:
- Milvus delete, Postgres delete, and storage delete all fire concurrently
- If one fails, others may have already completed
- Errors are collected but no rollback attempted (lines 592-595)

### Collection Delete (`DELETE /collections/{name}`)

**File:** `routers/collections.py:237-265`

| Step | Line | System | Operation | Reversible |
|------|------|--------|-----------|------------|
| 1 | 246 | Redis | `ingestion_queue.flush_collection()` | No |
| 2 | 249 | Milvus | `vector_store.delete_collection()` | No |
| 3 | 254 | Storage | `get_storage().delete_prefix()` | No |
| 4 | 258 | Postgres | `DELETE FROM collections WHERE name = $1` | No (cascades) |

### Ingestion Retry Cleanup

**File:** `queue.py:558-562`

```python
try:
    await vector_store.delete_by_document(job.collection_name, doc)
except Exception as cleanup_err:
    logger.warning(f"failed to clean up partial vectors: {cleanup_err!r}")
```

Cleanup failure is **logged and swallowed**. On next retry, duplicate vectors may be inserted.

## Failure Scenarios

| Operation | Failing Step | Orphaned State |
|-----------|-------------|----------------|
| Doc delete | Milvus fails | Vectors remain searchable, DB record gone, file gone |
| Doc delete | Postgres fails | Vectors deleted, DB record intact, file may be gone |
| Doc delete | Storage fails | Everything else clean, file leaked on disk/S3 |
| Collection delete | Milvus fails | Queue flushed, Milvus intact, storage/Postgres gone |
| Collection delete | Storage fails | Queue flushed, Milvus dropped, files leaked |
| Collection delete | Postgres fails | Queue + Milvus + storage cleaned, DB records remain |
| Ingestion retry | Vector cleanup fails | Partial + retry vectors coexist in Milvus |

## Current State

- No transaction spanning multiple systems
- No operation journal or pending state tracking
- No background reconciliation to detect orphans
- No compensation logic on failure
- The only background cleanup is `_cleanup_old_data()` in `queue.py:203-221` which only cleans `query_log` and `webhook_deliveries`, not orphaned data

## Proposed Fix

### Phase 1: Optimistic delete ordering + soft delete (moderate effort)

Reorder operations so the least-recoverable steps happen last, and use soft delete in Postgres for recoverability:

```python
async def delete_document(collection_name, document_id):
    # 1. Soft-delete in Postgres first (recoverable)
    await db.execute(
        "UPDATE documents SET status = 'deleting', updated_at = now() WHERE id = $1",
        document_id,
    )

    # 2. Delete vectors (not recoverable, but can be re-indexed)
    try:
        await vector_store.delete_by_document(collection_name, document_id)
    except Exception as e:
        logger.error(f"Milvus delete failed for {document_id}: {e!r}")
        # Mark for retry, don't hard-fail
        await db.execute(
            "UPDATE documents SET status = 'delete_failed', "
            "error_message = $1 WHERE id = $2",
            str(e), document_id,
        )
        raise HTTPException(status_code=500, detail="Delete partially failed, will retry")

    # 3. Delete storage file
    try:
        await get_storage().delete(row["file_path"])
    except Exception as e:
        logger.warning(f"Storage delete failed for {document_id}: {e!r}")
        # Non-critical — file is orphaned but harmless

    # 4. Hard-delete from Postgres (final step)
    await db.execute("DELETE FROM documents WHERE id = $1", document_id)
    await db.execute(
        "UPDATE collections SET document_count = (...) WHERE id = $1",
        collection["id"],
    )
```

### Phase 2: Background orphan reconciliation (moderate effort)

Add a periodic task (like `_cleanup_old_data`) that scans for inconsistencies:

```python
async def _reconcile_orphans(self) -> None:
    """Periodic scan for orphaned data across systems. Runs daily."""
    while True:
        try:
            await asyncio.sleep(86400)

            # 1. Find documents stuck in 'deleting' status > 1 hour
            stuck = await db.fetch(
                "SELECT * FROM documents WHERE status = 'deleting' "
                "AND updated_at < now() - interval '1 hour'"
            )
            for doc in stuck:
                try:
                    await vector_store.delete_by_document(
                        doc["collection_name"], str(doc["id"])
                    )
                    await get_storage().delete(doc["file_path"])
                    await db.execute(
                        "DELETE FROM documents WHERE id = $1", doc["id"]
                    )
                    logger.info(f"Reconciled stuck delete: {doc['id']}")
                except Exception as e:
                    logger.warning(f"Reconciliation failed for {doc['id']}: {e!r}")

            # 2. Find Milvus vectors with no matching Postgres document
            #    (requires Milvus scan — expensive, run weekly)

            # 3. Find storage files with no matching Postgres document
            #    (requires storage listing — expensive, run weekly)

        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"Reconciliation failed: {e!r}")
```

### Phase 3: Operation journal (higher effort)

Track each delete operation step in a Postgres table:

```sql
CREATE TABLE delete_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT NOT NULL,  -- 'document' or 'collection'
    target_id TEXT NOT NULL,
    step TEXT NOT NULL,  -- 'milvus', 'postgres', 'storage', 'redis'
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'completed', 'failed'
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
```

Each delete creates journal entries for all steps. A background worker processes pending entries and marks them complete. Failed entries are retried with backoff.

## Files to Modify

- `api/bigrag/routers/documents.py` — reorder delete steps, add soft delete
- `api/bigrag/routers/collections.py` — reorder delete steps
- `api/bigrag/services/queue.py` — add reconciliation task, improve retry cleanup
- `api/bigrag/database.py` — add migration for `delete_operations` table (Phase 3)
- `api/bigrag/models/document.py` — add 'deleting' and 'delete_failed' to status enum

## Testing

- Kill Milvus mid-delete and verify document enters 'delete_failed' status
- Kill storage mid-delete and verify graceful degradation
- Run reconciliation task and verify orphans are cleaned up
- Batch delete with partial failures — verify consistent final state
