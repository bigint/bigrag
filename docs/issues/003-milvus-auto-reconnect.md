# 003: No Milvus Auto-Reconnect on Connection Loss

**Status:** Open
**Severity:** High
**Component:** `api/bigrag/services/vector_store.py`

## Problem

If Milvus drops and recovers (restart, network blip, maintenance), the `MilvusClient` stays broken. All queries and ingestion operations fail until the entire bigRAG server is restarted. There is a `reconnect()` method but nothing calls it automatically.

## Current Architecture

### Connection lifecycle

```
main.py:85    vector_store.connect()      # Sync, during startup
                    ↓
              self.client = MilvusClient(uri=self.uri)
                    ↓
              [All operations use self.client via _run()]
                    ↓
main.py:116   vector_store.close()        # During shutdown
```

### How operations execute

All Milvus calls go through the async wrapper at `vector_store.py:29-31`:

```python
async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_get_executor(), partial(fn, *args, **kwargs))
```

This runs the blocking pymilvus call in a `ThreadPoolExecutor` (32 threads, `vector_store.py:23`). Exceptions propagate directly to the caller.

### Exception handling by method

| Method | Lines | Has try/except | Behavior on failure |
|--------|-------|----------------|---------------------|
| `create_collection()` | 73-102 | No | Exception propagates (500 to client) |
| `insert()` | 110-137 | No | Exception propagates (job retries) |
| `search()` | 139-174 | No | Exception propagates (500 to client) |
| `get_chunks()` | 176-196 | No | Exception propagates (500 to client) |
| `delete_by_document()` | 198-204 | No | Exception propagates |
| `delete_by_ids()` | 206-209 | No | Exception propagates |
| `text_search()` | 211-254 | **Yes** (catch-all) | Returns empty results, logs warning |
| `upsert()` | 256-281 | No | Exception propagates |

Only `text_search()` has any exception handling — and it swallows all errors, returning empty results indistinguishable from "no matches."

### pymilvus exception types

```
pymilvus.exceptions.MilvusException          # Base — connection lost, network timeout
    ├── ConnectionError                       # TRANSIENT — retry helps
    ├── DescribeCollectionException           # Collection not found — may be permanent
    ├── ParamError                            # Bad parameters — PERMANENT
    ├── SchemaError                           # Schema issues — PERMANENT
    └── DataError                             # Data issues — PERMANENT
```

### Existing reconnect() method

```python
# vector_store.py:49-57
def reconnect(self) -> None:
    logger.warning(f"Reconnecting to Milvus at {self.uri}")
    try:
        if self.client:
            self.client.close()
    except Exception:
        pass
    self.client = MilvusClient(uri=self.uri)
    logger.info(f"Reconnected to Milvus at {self.uri}")
```

**Problems:**
1. It's synchronous — can't be called from async context where failures occur
2. Nothing calls it — no automatic trigger on connection errors
3. No validation that the new connection actually works

## Impact

- Milvus restart during operation makes all queries return 500 errors
- Ingestion workers fail and retry, wasting all 3 attempts on connection errors
- The only recovery is restarting the entire bigRAG server
- No alert or log message indicates "Milvus connection lost, needs restart"
- Health check (`/health/ready`) will detect it but can't fix it

## Proposed Fix

### Phase 1: Retry wrapper with auto-reconnect (recommended)

Add a retry-capable wrapper that detects transient Milvus errors and reconnects:

```python
import pymilvus.exceptions as milvus_exc

_TRANSIENT_ERRORS = (
    milvus_exc.MilvusException,
    ConnectionError,
    TimeoutError,
    OSError,
)

_PERMANENT_ERRORS = (
    milvus_exc.ParamError,
    milvus_exc.SchemaError,
)


async def _run_with_retry(self, fn, *args, max_retries=2, **kwargs):
    """Execute a Milvus operation with automatic reconnection on transient failure."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await _run(fn, *args, **kwargs)
        except _PERMANENT_ERRORS:
            raise  # Don't retry bad queries
        except _TRANSIENT_ERRORS as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Milvus operation failed (attempt {attempt + 1}/{max_retries + 1}): "
                    f"{e!r}, reconnecting..."
                )
                try:
                    await asyncio.to_thread(self.reconnect)
                except Exception as re_err:
                    logger.error(f"Milvus reconnect failed: {re_err!r}")
                await asyncio.sleep(min(2 ** attempt, 10))
            else:
                raise
    raise last_error  # unreachable but satisfies type checker
```

Then update all methods to use it:

```python
async def search(self, collection, query_embedding, top_k=10, filters=None, ...):
    col = self._col(collection)
    results = await self._run_with_retry(
        self.client.search,
        collection_name=col,
        data=[query_embedding],
        limit=top_k,
        ...
    )
    ...
```

### Phase 2: Make reconnect async-safe

```python
async def areconnect(self) -> None:
    """Async-safe reconnect — runs blocking MilvusClient creation in thread."""
    logger.warning(f"Reconnecting to Milvus at {self.uri}")
    try:
        if self.client:
            await asyncio.to_thread(self.client.close)
    except Exception:
        pass
    self.client = await asyncio.to_thread(MilvusClient, uri=self.uri)
    # Verify connection works
    await _run(self.client.list_collections)
    logger.info(f"Reconnected to Milvus at {self.uri}")
```

### Phase 3: Fix text_search error swallowing

```python
async def text_search(self, collection, query_terms, top_k=10, filters=None):
    ...
    try:
        results = await self._run_with_retry(
            self.client.query, ...
        )
    except _PERMANENT_ERRORS as e:
        logger.warning(f"text_search query error: {e!r}")
        return []  # Bad filter syntax, return empty
    # Let transient errors propagate after retry exhaustion
    ...
```

### Phase 4: Executor health monitoring (optional)

Add observability to the thread pool:

```python
def _executor_stats(self) -> dict:
    ex = _get_executor()
    return {
        "threads": ex._max_workers,
        "active": len(ex._threads),
        "queue_size": ex._work_queue.qsize(),
    }
```

Expose in `/v1/stats` or `/health/ready` to detect pool exhaustion.

## Classifying Errors

Key decision: which pymilvus errors are transient vs permanent.

| Exception | Transient | Action |
|-----------|-----------|--------|
| `MilvusException` (generic) | Yes | Reconnect + retry |
| `ConnectionError` | Yes | Reconnect + retry |
| `DescribeCollectionException` | Maybe | If "can't find collection" — permanent. If connection issue — retry |
| `ParamError` | No | Raise immediately |
| `SchemaError` | No | Raise immediately |
| `DataError` | No | Raise immediately |
| Python `TimeoutError` | Yes | Retry (may not need reconnect) |
| Python `OSError` | Yes | Reconnect + retry |

The tricky case is `DescribeCollectionException` which can mean either "collection doesn't exist" (permanent) or "connection lost during describe" (transient). Check the error message to distinguish:

```python
if "can't find collection" in str(e):
    raise  # Permanent
else:
    # Transient, retry
```

## Files to Modify

- `api/bigrag/services/vector_store.py` — add `_run_with_retry`, `areconnect`, update all public methods
- `api/bigrag/main.py` — optionally expose executor stats in health endpoint

## Testing

- Start bigRAG, stop Milvus, verify queries fail with clear error
- Restart Milvus, verify auto-reconnect on next operation
- Verify permanent errors (bad filter) are not retried
- Load test: kill Milvus under load, verify recovery within 2-3 retries
- Verify thread pool doesn't deadlock during reconnection
