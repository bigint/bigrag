from __future__ import annotations

from bigrag.logging import get_logger
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")

QUEUE_KEY = "bigrag:ingestion:queue"
PROCESSING_KEY = "bigrag:ingestion:processing"
DEAD_LETTER_KEY = "bigrag:ingestion:dead"
STATS_KEY = "bigrag:ingestion:stats"
LEASE_KEY_PREFIX = "bigrag:ingestion:lease:"
COLLECTION_EPOCH_KEY_PREFIX = "bigrag:ingestion:collection_epoch:"
DOCUMENT_EPOCH_KEY_PREFIX = "bigrag:ingestion:document_epoch:"
LEASE_TTL_SECONDS = 30 * 60

ENQUEUE_LUA = """
local depth = redis.call('LLEN', KEYS[1])
if depth >= tonumber(ARGV[2]) then
  return -1
end
redis.call('LPUSH', KEYS[1], ARGV[1])
redis.call('HINCRBY', KEYS[2], 'queued', 1)
return redis.call('LLEN', KEYS[1])
"""

FLUSH_LUA = """
local items = redis.call('LRANGE', KEYS[1], 0, -1)
local kept = {}
local removed = 0
for _, raw in ipairs(items) do
  local ok, decoded = pcall(cjson.decode, raw)
  if ok and decoded['collection_name'] == ARGV[1] then
    removed = removed + 1
  else
    table.insert(kept, raw)
  end
end
redis.call('DEL', KEYS[1])
if #kept > 0 then
  redis.call('RPUSH', KEYS[1], unpack(kept))
end
return removed
"""


class IngestionCancelledError(RuntimeError):
    pass


def lease_key(job_id: str) -> str:
    return f"{LEASE_KEY_PREFIX}{job_id}"


def collection_epoch_key(collection_name: str) -> str:
    return f"{COLLECTION_EPOCH_KEY_PREFIX}{collection_name}"


def document_epoch_key(document_id: str) -> str:
    return f"{DOCUMENT_EPOCH_KEY_PREFIX}{document_id}"


async def recover_stuck_jobs(redis) -> int:
    items = await redis.lrange(PROCESSING_KEY, 0, -1)
    recovered = 0
    for raw in items:
        try:
            job = IngestionJob.deserialize(raw)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "queue: malformed processing payload, dropping",
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
            await redis.lrem(PROCESSING_KEY, 1, raw)
            continue
        if await redis.exists(lease_key(job.job_id)):
            continue
        await redis.lrem(PROCESSING_KEY, 1, raw)
        await redis.lpush(QUEUE_KEY, raw)
        recovered += 1
    if recovered > 0:
        await redis.hset(STATS_KEY, "processing", 0)
    return recovered


async def epoch_value(redis, key: str) -> int:
    if not redis:
        return 0
    raw = await redis.get(key)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def collection_epoch(redis, collection_name: str) -> int:
    return await epoch_value(redis, collection_epoch_key(collection_name))


async def document_epoch(redis, document_id: str) -> int:
    return await epoch_value(redis, document_epoch_key(document_id))


async def ensure_job_current(redis, job: IngestionJob) -> None:
    collection_value = await collection_epoch(redis, job.collection_name)
    if collection_value != job.collection_epoch:
        raise IngestionCancelledError(f"Ingestion cancelled for collection '{job.collection_name}'")
    document_value = await document_epoch(redis, job.document_id)
    if document_value != job.document_epoch:
        raise IngestionCancelledError(f"Ingestion cancelled for document '{job.document_id}'")


async def enqueue_job(redis, job: IngestionJob, queue_max_depth: int) -> int:
    return int(
        await redis.eval(
            ENQUEUE_LUA,
            2,
            QUEUE_KEY,
            STATS_KEY,
            job.serialize(),
            queue_max_depth,
        )
    )


async def flush_collection_jobs(redis, collection_name: str) -> int:
    removed = await redis.eval(
        FLUSH_LUA,
        1,
        QUEUE_KEY,
        collection_name,
    )
    return int(removed)


async def cancel_collection_jobs(redis, collection_name: str) -> int:
    removed = await flush_collection_jobs(redis, collection_name)
    await redis.incr(collection_epoch_key(collection_name))
    return removed


async def cancel_document_jobs(redis, document_ids: list[str]) -> None:
    pipe = redis.pipeline(transaction=False)
    for document_id in document_ids:
        pipe.incr(document_epoch_key(document_id))
    await pipe.execute()


async def queue_stats(redis) -> dict:
    raw = await redis.hgetall(STATS_KEY)
    pending = await redis.llen(QUEUE_KEY)
    processing = await redis.llen(PROCESSING_KEY)
    return {
        "queued": int(raw.get(b"queued", 0)),
        "completed": int(raw.get(b"completed", 0)),
        "failed": int(raw.get(b"failed", 0)),
        "pending": pending,
        "processing": processing,
    }
