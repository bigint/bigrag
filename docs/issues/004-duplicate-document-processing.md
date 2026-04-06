# 004: Duplicate Document Processing

**Status:** Open
**Severity:** High
**Component:** `api/bigrag/services/queue.py`, `api/bigrag/routers/documents.py`

## Problem

There is no document-level locking in the ingestion pipeline. Multiple workers can process the same document concurrently, resulting in duplicated vectors in Milvus and incorrect chunk counts in Postgres. This happens during reprocessing, crash recovery, and retry races.

## Scenarios

### Scenario 1: Reprocess while processing

**Trigger:** User calls `POST /documents/{id}/reprocess` while the document is actively being ingested.

**Code path:**

```
[Worker-0: _process_job]               [API: reprocess_document]
queue.py:500  UPDATE status='processing'
queue.py:513  Converting document...
                                        documents.py:295  delete_by_document()  ← deletes vectors mid-insert
                                        documents.py:297  UPDATE status='pending', chunk_count=0
                                        documents.py:303  enqueue(new job)
queue.py:447  vector_store.insert()   ← inserts chunks into a collection where some were just deleted
queue.py:517  UPDATE status='ready'   ← overwrites the 'pending' from reprocess
```

**Result:**
- Vectors in Milvus are in partial state (some deleted, some inserted)
- Document shows `status='ready'` with wrong `chunk_count`
- The reprocess job runs later and inserts a second set of vectors
- Document ends up with 2x the expected vectors

**Guard:** None. `reprocess_document` at `documents.py:269` does not check if the document is currently being processed.

### Scenario 2: Retry overlap

**Trigger:** Worker fails during processing, job is re-enqueued, new worker picks it up before the original finishes cleanup.

**Code path:**

```
[Worker-0: _process_job]               [Worker-1: picks up retry]
queue.py:560  delete_by_document()      
queue.py:581  enqueue(job)            → job enters QUEUE_KEY
                                        queue.py:285  blmove picks up same job
                                        queue.py:500  UPDATE status='processing'
queue.py:295  lrem(PROCESSING_KEY)      queue.py:513  Converting...
                                        queue.py:447  insert() ← inserting vectors
```

**Result:**
- There's a window between `enqueue()` (line 581) and `lrem()` (line 295) where the retry can start
- If Worker-1 picks up the job during this window, both workers are active on the same document
- `blmove` is atomic for a single call, but the re-enqueued job is a separate item

**Why this works (mostly):** Each job has a unique `job_id` (UUID, `queue.py:140`), so the serialized bytes differ. `lrem` at line 295 removes the correct copy. But both workers can still process the same `document_id` concurrently.

### Scenario 3: Crash recovery with partial vectors

**Trigger:** Worker is killed (OOM, SIGKILL) during vector insertion.

**Code path:**

```
[Worker-0: _process_job, killed at line 447]
  - Inserted 50 of 100 chunks into Milvus
  - DB shows status='processing', chunk_count=0
  - Job stays in PROCESSING_KEY (lrem never executed)

[Server restart]
  queue.py:223  _recover_stuck_jobs()
  - Moves job from PROCESSING_KEY back to QUEUE_KEY
  - Does NOT clean up partial vectors in Milvus

[Worker-1: picks up recovered job]
  queue.py:447  insert() → inserts 100 chunks
  - Milvus now has 150 vectors (50 orphaned + 100 new)
  - DB shows chunk_count=100
  - collection document_count incremented (may have been incremented before too)
```

**Result:**
- Milvus has 50 orphaned vectors from the crashed attempt
- `chunk_count` in Postgres only reflects the successful attempt (100)
- Search results may return duplicates from the orphaned chunks
- `document_count` on the collection may be wrong

**Guard:** `_recover_stuck_jobs()` at `queue.py:223-232` only moves jobs back to the queue. It does not call `delete_by_document()` to clean up partial state.

### Scenario 4: Concurrent uploads (safe)

Two rapid uploads of the same file create different `doc_id` values (UUID, `documents.py:117`). They get separate storage keys, DB records, and queue jobs. No conflict.

## Root Cause

No mutual exclusion on `document_id` during processing. The queue guarantees single delivery of a **job**, but not single processing of a **document**.

## Proposed Fix

### Phase 1: Document-level Redis lock (recommended)

Use a Redis lock (SET NX with expiry) to prevent concurrent processing of the same document:

```python
LOCK_PREFIX = "bigrag:doc_lock:"
LOCK_TTL = 600  # 10 minutes, must exceed max processing time

async def _acquire_doc_lock(self, document_id: str) -> bool:
    """Acquire an exclusive lock for processing a document."""
    key = f"{LOCK_PREFIX}{document_id}"
    acquired = await self._redis.set(key, "1", nx=True, ex=LOCK_TTL)
    return bool(acquired)

async def _release_doc_lock(self, document_id: str) -> None:
    """Release the processing lock for a document."""
    key = f"{LOCK_PREFIX}{document_id}"
    await self._redis.delete(key)

async def _extend_doc_lock(self, document_id: str) -> None:
    """Extend lock TTL during long processing."""
    key = f"{LOCK_PREFIX}{document_id}"
    await self._redis.expire(key, LOCK_TTL)
```

Update `_process_job` to acquire lock before processing:

```python
async def _process_job(self, worker_id, job):
    doc = job.document_id

    if not await self._acquire_doc_lock(doc):
        logger.warning(f"[worker-{worker_id}] doc={doc} already locked, skipping")
        # Re-enqueue with delay so the lock holder can finish
        await asyncio.sleep(5)
        await self.enqueue(job)
        return

    try:
        # ... existing processing logic ...
    finally:
        await self._release_doc_lock(doc)
```

For long documents, extend the lock periodically in `_chunk_and_embed`:

```python
# Inside the batch loop
if batch_num % 5 == 0:
    await self._extend_doc_lock(job.document_id)
```

### Phase 2: Guard reprocess against active processing

Add a status check in `reprocess_document`:

```python
# documents.py, reprocess_document
if row["status"] == "processing":
    raise HTTPException(
        status_code=409,
        detail="Document is currently being processed. Wait for completion or delete and re-upload."
    )
```

### Phase 3: Clean partial vectors on recovery

Update `_recover_stuck_jobs` to clean up before re-enqueueing:

```python
async def _recover_stuck_jobs(self) -> int:
    count = 0
    while True:
        data = await self._redis.lmove(
            PROCESSING_KEY, QUEUE_KEY, src="RIGHT", dest="LEFT"
        )
        if data is None:
            break
        count += 1

        # Clean up partial vectors from the crashed job
        try:
            job = IngestionJob.deserialize(data)
            from bigrag.services.vector_store import vector_store
            await vector_store.delete_by_document(
                job.collection_name, job.document_id
            )
            logger.info(f"[recovery] cleaned partial vectors for doc={job.document_id}")
        except Exception as e:
            logger.warning(f"[recovery] vector cleanup failed: {e!r}")

    if count > 0:
        await self._redis.hset(STATS_KEY, "processing", 0)
    return count
```

### Phase 4: Idempotent vector insertion (defensive)

Use the vector ID scheme `{document_id}_{chunk_index}` (already done at `queue.py:444`). Before inserting, delete existing vectors for the document:

```python
# In _chunk_and_embed, before the batch loop
await vector_store.delete_by_document(job.collection_name, job.document_id)
```

This makes ingestion idempotent — running it twice produces the same result. Combined with the document lock, this handles crash recovery gracefully.

## Redis Lock Considerations

- **TTL must exceed max processing time.** A 1GB PDF can take 5+ minutes. Use 600s (10 min) with periodic extension.
- **Lock key cleanup.** If the server crashes, locks expire via TTL. No manual cleanup needed.
- **Lock contention.** If a lock is held, the waiting job re-enqueues itself with a delay. This wastes one queue cycle but is simple and correct.
- **Redis down.** If Redis is unreachable, lock acquisition fails, job is re-enqueued. Processing stalls but no data corruption.

## Files to Modify

- `api/bigrag/services/queue.py` — add lock methods, update `_process_job`, update `_recover_stuck_jobs`, add pre-insert cleanup
- `api/bigrag/routers/documents.py` — add status guard on `reprocess_document`

## Testing

- Call reprocess while document is processing — verify 409 response
- Kill a worker mid-ingestion, restart server — verify partial vectors cleaned and document re-processes correctly
- Submit same document for processing twice rapidly — verify lock prevents concurrent execution
- Verify lock expires if server crashes (check Redis key TTL)
- Load test with concurrent uploads and reprocessing to verify no duplicate vectors
