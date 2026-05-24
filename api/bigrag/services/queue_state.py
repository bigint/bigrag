from __future__ import annotations

from bigrag.logging import get_logger
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")

QUEUE_KEY = "bigrag:ingestion:queue"
PROCESSING_KEY = "bigrag:ingestion:processing"
DEAD_LETTER_KEY = "bigrag:ingestion:dead"
RETRY_KEY = "bigrag:ingestion:retry"
STATS_KEY = "bigrag:ingestion:stats"
LEASE_KEY_PREFIX = "bigrag:ingestion:lease:"
COLLECTION_EPOCH_KEY_PREFIX = "bigrag:ingestion:collection_epoch:"
DOCUMENT_EPOCH_KEY_PREFIX = "bigrag:ingestion:document_epoch:"
LEASE_TTL_SECONDS = 30 * 60
LEASE_RENEW_INTERVAL_SECONDS = 60
LEASE_ACTIVE_MIN_TTL_SECONDS = LEASE_TTL_SECONDS - LEASE_RENEW_INTERVAL_SECONDS * 4

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


class QueueFullError(ValueError):
    pass


def lease_key(job_id: str) -> str:
    return f"{LEASE_KEY_PREFIX}{job_id}"


def collection_epoch_key(collection_name: str) -> str:
    return f"{COLLECTION_EPOCH_KEY_PREFIX}{collection_name}"


def document_epoch_key(document_id: str) -> str:
    return f"{DOCUMENT_EPOCH_KEY_PREFIX}{document_id}"


async def recover_stuck_jobs(redis) -> list[IngestionJob]:
    items = await redis.lrange(PROCESSING_KEY, 0, -1)
    recovered: list[IngestionJob] = []
    parsed: list[tuple[bytes, IngestionJob]] = []
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
        parsed.append((raw, job))
    if parsed:
        pipe = redis.pipeline(transaction=False)
        for _, job in parsed:
            pipe.ttl(lease_key(job.job_id))
        ttls = await pipe.execute()
        for (raw, job), ttl in zip(parsed, ttls, strict=True):
            if ttl >= LEASE_ACTIVE_MIN_TTL_SECONDS:
                continue
            await redis.lrem(PROCESSING_KEY, 1, raw)
            recovered.append(job)
    if recovered:
        remaining = await redis.llen(PROCESSING_KEY)
        await redis.hset(STATS_KEY, "processing", remaining)
    return recovered


async def processing_lease_active(redis, job_id: str) -> bool:
    ttl = await redis.ttl(lease_key(job_id))
    return ttl >= LEASE_ACTIVE_MIN_TTL_SECONDS


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
    processing_items = await redis.lrange(PROCESSING_KEY, 0, -1)
    processing = len(processing_items)
    leased_processing = 0
    stale_processing = 0
    for item in processing_items:
        try:
            job = IngestionJob.deserialize(item)
        except (ValueError, TypeError, KeyError):
            stale_processing += 1
            continue
        if await processing_lease_active(redis, job.job_id):
            leased_processing += 1
        else:
            stale_processing += 1
    return {
        "queued": int(raw.get(b"queued", 0)),
        "completed": int(raw.get(b"completed", 0)),
        "failed": int(raw.get(b"failed", 0)),
        "pending": pending,
        "processing": processing,
        "retrying": await redis.zcard(RETRY_KEY),
        "dead_lettered": await redis.llen(DEAD_LETTER_KEY),
        "leased_processing": leased_processing,
        "stale_processing": stale_processing,
    }
