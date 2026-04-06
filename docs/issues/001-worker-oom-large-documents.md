# 001: Worker OOM on Large Documents

**Status:** Open
**Severity:** High
**Component:** `api/bigrag/services/queue.py`, `api/bigrag/services/storage.py`

## Problem

The ingestion pipeline loads entire documents into memory at every stage. A single 1GB PDF can consume 5-6GB of RAM during Docling conversion. With 4 workers, a batch of large documents can easily OOM-kill the process with no cleanup of partial state.

## Memory Lifecycle

| Stage | Method | Peak Memory | Duration |
|-------|--------|-------------|----------|
| Load from storage | `storage.get()` at `queue.py:327` | 1 GB (full file as `bytes`) | instant |
| Write to temp + Docling parse | `_write_and_convert()` at `queue.py:330-339` | 5-6 GB (file + Docling internal structures + OCR) | 30-120s |
| Export to markdown | `result.document.export_to_markdown()` at `queue.py:368` | +0.3-0.5 GB (markdown string) | 1-5s |
| Chunk text | `_chunk_text()` at `queue.py:415` | +0.3-0.7 GB (paragraphs list + chunks list) | <1s |
| Batch embedding | `embedding_model.embed()` at `queue.py:440` | ~0.5 MB per batch (128 chunks) | 5-30s per batch |

**Total peak: ~6 GB for a 1 GB input PDF** during Docling conversion (Stage 2).

## Root Causes

### 1. Storage loads entire file into memory

`storage.py:59` (LocalStorage) calls `path.read_bytes()` — full file into a single `bytes` object. S3Storage does the same at `storage.py:146` with `await stream.read()`.

```python
# queue.py:327
file_data = await get_storage().get(job.file_path)  # 1 GB in memory
```

### 2. File data coexists with Docling structures

At `queue.py:333`, the file bytes are written to a temp file, but `file_data` stays in scope until the function returns at line 383. During Docling conversion, both the original bytes and Docling's internal document tree coexist in memory.

### 3. Docling does not support streaming

`DocumentConverter.convert()` loads the entire PDF, runs layout analysis (ML models), OCR, and builds a complete document tree in memory. There is no page-by-page or streaming API. `export_to_markdown()` returns the entire markdown as one string.

### 4. No memory limit per worker

Workers have no resource limits. 4 workers can each load a large document simultaneously. No backpressure mechanism based on available memory.

## Impact

- Worker process gets OOM-killed by the OS (SIGKILL)
- `finally` block at `queue.py:295` may or may not execute
- Partial vectors remain in Milvus
- Document stuck in "processing" status forever (until recovery on restart)
- Other workers in the same process are also killed

## Proposed Fix

### Phase 1: Reduce peak memory (moderate effort)

**Release file bytes before Docling conversion starts:**

```python
async def _convert_document(self, job, prefix):
    file_data = await get_storage().get(job.file_path)
    suffix = Path(job.file_path).suffix

    # Write to temp file and release bytes immediately
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(file_data)
    tmp.close()
    del file_data  # Release 1 GB before Docling starts
    gc.collect()

    try:
        converter = _get_docling_converter()
        result = await asyncio.wait_for(
            asyncio.to_thread(converter.convert, tmp.name),
            timeout=settings.conversion_timeout,
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    text = result.document.export_to_markdown()
    del result  # Release Docling structures
    gc.collect()

    return text
```

**Saves:** ~1 GB by releasing file bytes before conversion. Peak drops from ~6 GB to ~5 GB.

### Phase 2: File size guard (low effort)

Reject documents above a configurable threshold at upload time and skip ingestion for files that would exceed per-worker memory:

```python
# In _process_job, before conversion
file_size = await get_storage().size(job.file_path)  # New method needed
if file_size > settings.max_ingestion_file_size:
    raise ValueError(f"File too large for ingestion: {file_size} bytes")
```

Add `BIGRAG_MAX_INGESTION_FILE_SIZE` config (default: 500 MB).

### Phase 3: Stream from storage to temp file (moderate effort)

Add a streaming `get_to_file()` method to `StorageBackend` that writes directly to a temp file without loading into memory:

```python
class StorageBackend:
    async def get_to_file(self, key: str, dest: Path) -> int:
        """Stream storage object directly to a local file. Returns bytes written."""
        ...

class LocalStorage(StorageBackend):
    async def get_to_file(self, key: str, dest: Path) -> int:
        src = self._safe_path(key)
        # Use shutil.copyfile in thread — no memory buffering
        await asyncio.to_thread(shutil.copyfile, src, dest)
        return dest.stat().st_size

class S3Storage(StorageBackend):
    async def get_to_file(self, key: str, dest: Path) -> int:
        client = await self._get_client()
        resp = await client.get_object(Bucket=self._bucket, Key=key)
        written = 0
        async with resp["Body"] as stream:
            with open(dest, "wb") as f:
                while chunk := await stream.read(8192):
                    f.write(chunk)
                    written += len(chunk)
        return written
```

Then in `_convert_document`, use `get_to_file()` instead of `get()` — file goes directly from storage to temp file, never enters Python memory.

### Phase 4: Docling page-by-page processing (high effort, depends on upstream)

Monitor Docling releases for streaming/iterative conversion APIs. If available:
- Process PDF page by page
- Chunk and embed incrementally
- Memory usage becomes proportional to single page, not entire document

This is blocked on Docling upstream changes.

## Files to Modify

- `api/bigrag/services/storage.py` — add `get_to_file()` method
- `api/bigrag/services/queue.py` — restructure `_convert_document()`, add file size guard
- `api/bigrag/config.py` — add `max_ingestion_file_size` setting
- `api/bigrag/routers/documents.py` — optionally warn on upload if file is very large

## Testing

- Upload a 500MB+ PDF and monitor RSS memory of the worker process
- Verify temp files are cleaned up after conversion (both success and failure paths)
- Verify `gc.collect()` calls actually reduce memory (use `tracemalloc` snapshots)
- Test with 4 concurrent large uploads to verify no OOM under load
