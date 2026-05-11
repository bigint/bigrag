from __future__ import annotations

import asyncio
import time
import uuid

import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services import queue_conversion, queue_embedding, queue_state
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")

QUEUE_KEY = queue_state.QUEUE_KEY
PROCESSING_KEY = queue_state.PROCESSING_KEY
DEAD_LETTER_KEY = queue_state.DEAD_LETTER_KEY
STATS_KEY = queue_state.STATS_KEY
LEASE_KEY_PREFIX = queue_state.LEASE_KEY_PREFIX
COLLECTION_EPOCH_KEY_PREFIX = queue_state.COLLECTION_EPOCH_KEY_PREFIX
DOCUMENT_EPOCH_KEY_PREFIX = queue_state.DOCUMENT_EPOCH_KEY_PREFIX
IngestionCancelledError = queue_state.IngestionCancelledError

_LEASE_TTL_SECONDS = queue_state.LEASE_TTL_SECONDS
_EMBEDDING_TIMEOUT_SECONDS = queue_embedding.EMBEDDING_TIMEOUT_SECONDS
_PERMANENT_ERRORS = queue_embedding.PERMANENT_ERRORS
_PDF_OCR_CHUNK_PAGES = queue_conversion.PDF_OCR_CHUNK_PAGES
_PDF_OCR_PROGRESS_START = queue_conversion.PDF_OCR_PROGRESS_START
_PDF_OCR_PROGRESS_END = queue_conversion.PDF_OCR_PROGRESS_END
_docling_result_text = queue_conversion.docling_result_text
_embed_with_cache = queue_embedding.embed_with_cache
_delete_document_vectors_after_failure = queue_embedding.delete_document_vectors_after_failure
_lease_key = queue_state.lease_key
_collection_epoch_key = queue_state.collection_epoch_key
_document_epoch_key = queue_state.document_epoch_key

__all__ = [
    "COLLECTION_EPOCH_KEY_PREFIX",
    "DEAD_LETTER_KEY",
    "DOCUMENT_EPOCH_KEY_PREFIX",
    "IngestionCancelledError",
    "IngestionQueue",
    "LEASE_KEY_PREFIX",
    "PROCESSING_KEY",
    "QUEUE_KEY",
    "STATS_KEY",
    "_EMBEDDING_TIMEOUT_SECONDS",
    "_PERMANENT_ERRORS",
    "_PDF_OCR_CHUNK_PAGES",
    "_PDF_OCR_PROGRESS_END",
    "_PDF_OCR_PROGRESS_START",
    "_collection_epoch_key",
    "_delete_document_vectors_after_failure",
    "_docling_result_text",
    "_document_epoch_key",
    "_embed_with_cache",
    "_lease_key",
    "ingestion_queue",
]


class IngestionQueue:
    def __init__(self, num_workers: int = 4) -> None:
        self._num_workers = num_workers
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._redis: aioredis.Redis | None = None
        self._vector_store = None

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

        self._running = True
        recovered = await self._recover_stuck_jobs()
        if recovered:
            logger.info("queue recovered stuck jobs", recovered=recovered)

        for i in range(self._num_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        logger.info("queue started workers", workers=self._num_workers)

    async def resize_workers(self, num_workers: int) -> None:
        target = max(1, int(num_workers))
        if not self._running:
            self._num_workers = target
            return
        current = len(self._workers)
        if target == current:
            self._num_workers = target
            return
        if target > current:
            for worker_id in range(current, target):
                task = asyncio.create_task(self._worker(worker_id))
                self._workers.append(task)
            self._num_workers = target
            logger.info("queue resized workers", previous=current, target=target)
            return
        removed = self._workers[target:]
        self._workers = self._workers[:target]
        for task in removed:
            task.cancel()
        await asyncio.gather(*removed, return_exceptions=True)
        self._num_workers = target
        logger.info("queue resized workers", previous=current, target=target)

    async def stop(self) -> None:
        self._running = False
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._redis:
            await self._redis.aclose()
        logger.info("[queue] all workers stopped")

    async def _recover_stuck_jobs(self) -> int:
        return await queue_state.recover_stuck_jobs(self._redis)

    _ENQUEUE_LUA = queue_state.ENQUEUE_LUA
    _FLUSH_LUA = queue_state.FLUSH_LUA

    async def _epoch_value(self, key: str) -> int:
        return await queue_state.epoch_value(self._redis, key)

    async def _collection_epoch(self, collection_name: str) -> int:
        return await queue_state.collection_epoch(self._redis, collection_name)

    async def _document_epoch(self, document_id: str) -> int:
        return await queue_state.document_epoch(self._redis, document_id)

    async def _ensure_job_current(self, job: IngestionJob) -> None:
        await queue_state.ensure_job_current(self._redis, job)

    async def enqueue(self, job: IngestionJob) -> None:
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
        pending = await queue_state.enqueue_job(self._redis, job, queue_max_depth)
        if pending == -1:
            raise ValueError("Ingestion queue is full. Try again later.")
        logger.info(
            "queue enqueued job",
            job=job.job_id,
            doc=job.document_id,
            collection=job.collection_name,
            pending=pending,
        )

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
        return await queue_state.queue_stats(self._redis)

    async def _worker(self, worker_id: int) -> None:
        logger.info("worker started", worker_id=worker_id)
        while self._running:
            try:
                from bigrag.services.maintenance import is_active

                if await is_active():
                    await asyncio.sleep(1)
                    continue
                data = await self._redis.blmove(
                    QUEUE_KEY, PROCESSING_KEY, timeout=1, src="RIGHT", dest="LEFT"
                )
                if data is None:
                    continue
                if await is_active():
                    await self._redis.lrem(PROCESSING_KEY, 1, data)
                    await self._redis.rpush(QUEUE_KEY, data)
                    await asyncio.sleep(1)
                    continue

                job = IngestionJob.deserialize(data)
                logger.info(
                    "worker dequeued job",
                    worker_id=worker_id,
                    job=job.job_id,
                    doc=job.document_id,
                    collection=job.collection_name,
                    file_path=job.file_path,
                    attempt=job.attempt + 1,
                    max_attempts=job.max_attempts,
                )
                lease_key = _lease_key(job.job_id)
                await self._redis.set(lease_key, b"1", ex=_LEASE_TTL_SECONDS)
                try:
                    await self._process_job(worker_id, job)
                finally:
                    await self._redis.lrem(PROCESSING_KEY, 1, data)
                    await self._redis.delete(lease_key)
            except Exception as e:
                logger.error("worker loop error", worker_id=worker_id, error=repr(e))
                await asyncio.sleep(1)

        logger.info("worker stopped", worker_id=worker_id)

    def _emit(
        self,
        doc_id: str,
        step: str,
        status: str,
        msg: str,
        progress: float = 0.0,
        collection_name: str = "",
        **detail,
    ) -> None:
        logger.info(
            "ingestion event",
            doc=doc_id,
            collection=collection_name,
            step=step,
            status=status,
            progress=progress,
            message=msg,
            detail=detail,
        )
        event_bus.publish(
            IngestionEvent(
                document_id=doc_id,
                step=step,
                status=status,
                message=msg,
                progress=progress,
                detail=detail,
                collection_name=collection_name,
            )
        )

    _PLAIN_TEXT_EXTS = queue_conversion.PLAIN_TEXT_EXTS

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

    async def _convert_document(self, job: IngestionJob, prefix: str) -> str:
        return await queue_conversion.convert_document(
            job,
            prefix,
            emit=self._emit,
            ensure_job_current=self._ensure_job_current,
        )

    async def _chunk_and_embed(self, job: IngestionJob, text: str, prefix: str) -> tuple[int, int]:
        return await queue_embedding.chunk_and_embed(
            job,
            text,
            prefix,
            vector_store=self._vector_store,
            emit=self._emit,
            ensure_job_current=self._ensure_job_current,
        )

    async def _process_job(self, worker_id: int, job: IngestionJob) -> None:
        import sqlalchemy as sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import Document

        vector_store = self._vector_store
        if vector_store is None:
            from bigrag.services.vector_store import vector_store

        doc_uuid = uuid.UUID(job.document_id)

        async def _update_doc(**values) -> None:
            async with session_factory()() as session:
                await session.execute(
                    sa.update(Document).where(Document.id == doc_uuid).values(**values)
                )
                await session.commit()

        job.attempt += 1
        prefix = f"[worker-{worker_id}] [job={job.job_id}] [doc={job.document_id}]"
        doc = job.document_id

        await self._redis.hincrby(STATS_KEY, "processing", 1)
        logger.info(
            "job starting",
            prefix=prefix,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
        )
        self._emit(
            doc,
            "queued",
            "processing",
            "Starting ingestion",
            0.0,
            collection_name=job.collection_name,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
        )

        start_time = time.monotonic()

        try:
            await self._ensure_job_current(job)
            await _update_doc(status="processing")
            self._emit(
                doc,
                "processing",
                "processing",
                "Preparing document",
                0.05,
                collection_name=job.collection_name,
            )

            text = await self._convert_document(job, prefix)
            await self._ensure_job_current(job)
            total_inserted, total_expected = await self._chunk_and_embed(job, text, prefix)
            token_count = len(text) // 4

            if total_inserted == 0:
                raise RuntimeError(f"All {total_expected} chunk batches failed embedding/insert")

            partial_msg = (
                f"Partial: {total_inserted}/{total_expected} chunks embedded"
                if total_inserted < total_expected
                else None
            )

            async with session_factory()() as session:
                await session.execute(
                    sa.update(Document)
                    .where(Document.id == doc_uuid)
                    .values(
                        status="ready",
                        chunk_count=total_inserted,
                        token_count=token_count,
                        error_message=partial_msg,
                    )
                )
                await session.commit()

            from bigrag.services.retrieval import invalidate_collection_query_cache

            await invalidate_collection_query_cache(job.collection_name)
            total_elapsed = time.monotonic() - start_time
            await self._redis.hincrby(STATS_KEY, "completed", 1)
            await self._redis.hincrby(STATS_KEY, "processing", -1)
            logger.info(
                "job complete",
                prefix=prefix,
                chunks=total_inserted,
                elapsed=round(total_elapsed, 2),
            )
            self._emit(
                doc,
                "complete",
                "complete",
                f"Done — {total_inserted} chunks in {total_elapsed:.1f}s",
                1.0,
                collection_name=job.collection_name,
                chunks=total_inserted,
                elapsed=round(total_elapsed, 2),
            )
            event_bus.complete(doc)

        except Exception as e:
            total_elapsed = time.monotonic() - start_time
            await self._redis.hincrby(STATS_KEY, "processing", -1)
            logger.error(
                "job failed",
                prefix=prefix,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                error=repr(e),
                elapsed=round(total_elapsed, 2),
            )

            is_permanent = isinstance(e, _PERMANENT_ERRORS)

            if isinstance(e, IngestionCancelledError):
                await _delete_document_vectors_after_failure(
                    vector_store,
                    job.collection_name,
                    doc,
                    prefix=prefix,
                    log_message="failed to clean up cancelled vectors",
                )
                await _update_doc(status="failed", error_message=str(e))
                self._emit(
                    doc,
                    "cancelled",
                    "failed",
                    str(e),
                    0.0,
                    collection_name=job.collection_name,
                )
                event_bus.complete(doc)
            elif not is_permanent and job.attempt < job.max_attempts:
                await _delete_document_vectors_after_failure(
                    vector_store,
                    job.collection_name,
                    doc,
                    prefix=prefix,
                    log_message="failed to clean up partial vectors",
                )

                delay = min(2**job.attempt, 30)
                self._emit(
                    doc,
                    "retrying",
                    "processing",
                    f"Attempt {job.attempt} failed, retrying in {delay}s",
                    0.0,
                    collection_name=job.collection_name,
                    error=str(e),
                    attempt=job.attempt,
                    delay=delay,
                )
                await _update_doc(
                    status="pending",
                    error_message=f"Attempt {job.attempt} failed: {e}. Retrying...",
                )
                await self.enqueue(job)
            else:
                reason = (
                    "permanent error" if is_permanent else f"{job.max_attempts} attempts exhausted"
                )
                await self._redis.hincrby(STATS_KEY, "failed", 1)
                await self._redis.lpush(DEAD_LETTER_KEY, job.serialize())
                await self._redis.ltrim(DEAD_LETTER_KEY, 0, 999)
                await _update_doc(status="failed", error_message=str(e))
                logger.error("job permanently failed", prefix=prefix, reason=reason)
                self._emit(
                    doc,
                    "failed",
                    "failed",
                    str(e),
                    0.0,
                    collection_name=job.collection_name,
                    attempts=job.attempt,
                )
                event_bus.complete(doc)


ingestion_queue = IngestionQueue()
