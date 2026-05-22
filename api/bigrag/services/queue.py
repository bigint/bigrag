from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services import (
    queue_conversion,
    queue_embedding,
    queue_processing,
    queue_recovery,
    queue_state,
)
from bigrag.services.document_elements import ParsedDocument
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")

QUEUE_KEY = queue_state.QUEUE_KEY
PROCESSING_KEY = queue_state.PROCESSING_KEY
DEAD_LETTER_KEY = queue_state.DEAD_LETTER_KEY
RETRY_KEY = queue_state.RETRY_KEY
STATS_KEY = queue_state.STATS_KEY
LEASE_KEY_PREFIX = queue_state.LEASE_KEY_PREFIX
COLLECTION_EPOCH_KEY_PREFIX = queue_state.COLLECTION_EPOCH_KEY_PREFIX
DOCUMENT_EPOCH_KEY_PREFIX = queue_state.DOCUMENT_EPOCH_KEY_PREFIX
IngestionCancelledError = queue_state.IngestionCancelledError

_LEASE_TTL_SECONDS = queue_state.LEASE_TTL_SECONDS
_LEASE_RENEW_INTERVAL_SECONDS = queue_state.LEASE_RENEW_INTERVAL_SECONDS
_lease_key = queue_state.lease_key
_collection_epoch_key = queue_state.collection_epoch_key
_document_epoch_key = queue_state.document_epoch_key


class IngestionQueue:
    def __init__(self, num_workers: int = 4) -> None:
        self._num_workers = num_workers
        self._redis: aioredis.Redis | None = None
        self._vector_store = None

    @property
    def redis(self):
        return self._redis

    def bind_vector_store(self, vector_store) -> None:
        self._vector_store = vector_store

    async def connect(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(
            redis_url,
            decode_responses=False,
            max_connections=max(self._num_workers + 4, 260),
        )
        await self._redis.ping()
        logger.info("queue connected to redis", redis_url=redis_url)

    async def start(self, vector_store=None) -> None:
        if vector_store is not None:
            self._vector_store = vector_store

        recovered = await self._recover_stuck_jobs()
        if recovered:
            logger.info("queue recovered stuck jobs", recovered=recovered)
        logger.info("queue ready for dramatiq workers")

    async def resize_workers(self, num_workers: int) -> None:
        target = max(1, int(num_workers))
        self._num_workers = target
        logger.info("queue worker setting updated", target=target)

    async def stop(self) -> None:
        if self._redis:
            await self._redis.aclose()
        logger.info("[queue] all workers stopped")

    async def _recover_stuck_jobs(self) -> int:
        if self._redis is None:
            return 0
        return await queue_recovery.recover_stuck_jobs(self._redis)

    async def _epoch_value(self, key: str) -> int:
        return await queue_state.epoch_value(self._redis, key)

    async def _collection_epoch(self, collection_name: str) -> int:
        return await queue_state.collection_epoch(self._redis, collection_name)

    async def _document_epoch(self, document_id: str) -> int:
        return await queue_state.document_epoch(self._redis, document_id)

    async def _ensure_job_current(self, job: IngestionJob) -> None:
        await queue_state.ensure_job_current(self._redis, job)

    async def enqueue(self, job: IngestionJob) -> None:
        from bigrag.services.jobs.actors import enqueue_ingestion_job
        from bigrag.services.jobs.broker import INGESTION_QUEUE, queue_size
        from bigrag.services.maintenance import MaintenanceActiveError, ensure_writes_allowed
        from bigrag.services.runtime_settings import get_value

        try:
            await ensure_writes_allowed()
        except MaintenanceActiveError as exc:
            raise ValueError(str(exc)) from exc

        if job.attempt == 0:
            job.collection_epoch = await self._collection_epoch(job.collection_name)
            job.document_epoch = await self._document_epoch(job.document_id)
        queue_max_depth = await get_value("queue_max_depth")
        pending = await queue_size(INGESTION_QUEUE)
        if pending >= queue_max_depth:
            raise ValueError("Ingestion queue is full. Try again later.")
        enqueue_ingestion_job(job)
        if self._redis is not None:
            await self._redis.hincrby(STATS_KEY, "queued", 1)
        logger.info(f"{job.collection_name} | queued | {pending + 1} pending")

    async def flush_collection(self, collection_name: str) -> int:
        if not self._redis:
            return 0
        removed = await queue_state.flush_collection_jobs(self._redis, collection_name)
        if removed:
            logger.info("queue flushed jobs", collection=collection_name, removed=removed)
        return int(removed)

    async def cancel_collection(self, collection_name: str) -> int:
        if not self._redis:
            return 0
        removed = await queue_state.cancel_collection_jobs(self._redis, collection_name)
        logger.info("queue cancelled collection jobs", collection=collection_name, flushed=removed)
        return removed

    async def cancel_documents(self, document_ids: list[str]) -> None:
        if not self._redis:
            return
        await queue_state.cancel_document_jobs(self._redis, document_ids)
        logger.info("queue cancelled document jobs", count=len(document_ids))

    @property
    async def stats(self) -> dict:
        if self._redis is None:
            return {"queued": 0, "completed": 0, "failed": 0}
        from bigrag.services.jobs.broker import (
            INGESTION_QUEUE,
            dead_letter_key,
            delayed_messages_key,
            queue_size,
        )

        stats = await queue_state.queue_stats(self._redis)
        try:
            stats["pending"] = await queue_size(INGESTION_QUEUE)
        except Exception:
            logger.warning("queue stats: dramatiq queue size unavailable")
        if self._redis is not None:
            stats["retrying"] = await self._redis.hlen(delayed_messages_key(INGESTION_QUEUE))
            stats["dead_lettered"] = max(
                int(stats.get("dead_lettered") or 0),
                await self._redis.zcard(dead_letter_key(INGESTION_QUEUE)),
            )
        return stats

    async def _promote_due_retries(self) -> int:
        from bigrag.services.runtime_settings import get_value

        queue_max_depth = await get_value("queue_max_depth")
        promoted = await queue_state.promote_due_retries(
            self._redis,
            queue_max_depth=queue_max_depth,
        )
        if promoted:
            logger.info("queue promoted retry jobs", count=promoted)
        return promoted

    async def _renew_lease(self, job_id: str) -> None:
        lease_key = _lease_key(job_id)
        while True:
            await asyncio.sleep(_LEASE_RENEW_INTERVAL_SECONDS)
            try:
                await self._redis.set(lease_key, b"1", ex=_LEASE_TTL_SECONDS)
            except Exception as exc:
                logger.warning("queue lease renew failed", job=job_id, error=repr(exc))

    async def process_leased_job(self, worker_id: int | str, job: IngestionJob) -> None:
        if self._redis is None:
            raise RuntimeError("ingestion queue is not connected")
        raw = job.serialize()
        await self._redis.lpush(PROCESSING_KEY, raw)
        lease_key = _lease_key(job.job_id)
        await self._redis.set(lease_key, b"1", ex=_LEASE_TTL_SECONDS)
        lease_task = asyncio.create_task(self._renew_lease(job.job_id))
        try:
            await self._process_job(worker_id, job)
        finally:
            lease_task.cancel()
            try:
                await lease_task
            except asyncio.CancelledError:
                pass
            await self._redis.lrem(PROCESSING_KEY, 1, raw)
            await self._redis.delete(lease_key)

    def _emit(
        self,
        doc_id: str,
        step: str,
        status: str,
        msg: str,
        progress: float = 0.0,
        collection_name: str = "",
        **detail,
    ) -> IngestionEvent:
        progress_text = f"{round(progress * 100)}%"
        prefix = f"{collection_name} | " if collection_name else ""
        logger.info(f"{prefix}{progress_text} | {msg}")
        event = IngestionEvent(
            document_id=doc_id,
            step=step,
            status=status,
            message=msg,
            progress=progress,
            detail=detail,
            collection_name=collection_name,
        )
        event_bus.publish(event)
        return event

    async def _fanout_webhook_event(self, event: IngestionEvent) -> None:
        if event.step not in {"processing", "complete", "failed"}:
            return
        try:
            from bigrag.services.webhook import WebhookDispatcher

            await WebhookDispatcher()._handle_event(event)
        except Exception as exc:
            logger.warning(
                "webhook fanout failed",
                doc=event.document_id,
                step=event.step,
                error=repr(exc),
            )

    async def _ocr_scanned_pdf(
        self,
        *,
        file_data: bytes,
        suffix: str,
        job: IngestionJob,
        prefix: str,
        start_time: float,
    ) -> str:
        return await queue_conversion.ocr_scanned_pdf(
            file_data=file_data,
            suffix=suffix,
            job=job,
            prefix=prefix,
            start_time=start_time,
            emit=self._emit,
            ensure_job_current=self._ensure_job_current,
        )

    async def _convert_document(self, job: IngestionJob, prefix: str) -> ParsedDocument:
        return await queue_conversion.convert_document(
            job,
            prefix,
            emit=self._emit,
            ensure_job_current=self._ensure_job_current,
        )

    async def _chunk_and_embed(
        self,
        job: IngestionJob,
        parsed: ParsedDocument,
        prefix: str,
    ) -> tuple[int, int]:
        return await queue_embedding.chunk_and_embed(
            job,
            parsed,
            prefix,
            vector_store=self._vector_store,
            emit=self._emit,
            ensure_job_current=self._ensure_job_current,
        )

    async def _process_job(self, worker_id: int | str, job: IngestionJob) -> None:
        await queue_processing.process_job(self, worker_id, job)


ingestion_queue = IngestionQueue()
