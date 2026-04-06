from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import orjson
import redis.asyncio as aioredis

logger = logging.getLogger("bigrag.queue")

_docling_converter = None


def _get_docling_converter():
    global _docling_converter
    if _docling_converter is None:
        import os

        # Skip HuggingFace API calls when models are already cached locally
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        pdf_opts = PdfPipelineOptions()
        pdf_opts.do_ocr = True

        _docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=pdf_opts,
                )
            }
        )
    return _docling_converter


_PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)

QUEUE_KEY = "bigrag:ingestion:queue"
PROCESSING_KEY = "bigrag:ingestion:processing"
DEAD_LETTER_KEY = "bigrag:ingestion:dead"
STATS_KEY = "bigrag:ingestion:stats"


@dataclass
class IngestionEvent:
    document_id: str
    step: str
    status: str
    message: str
    progress: float = 0.0
    detail: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        data = {
            "document_id": self.document_id,
            "step": self.step,
            "status": self.status,
            "message": self.message,
            "progress": self.progress,
            **self.detail,
        }
        return f"data: {orjson.dumps(data).decode()}\n\n"


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[IngestionEvent | None]]] = {}

    def subscribe(self, document_id: str) -> asyncio.Queue[IngestionEvent | None]:
        q: asyncio.Queue[IngestionEvent | None] = asyncio.Queue()
        self._subs.setdefault(document_id, []).append(q)
        return q

    def unsubscribe(self, document_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(document_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subs.pop(document_id, None)

    def publish(self, event: IngestionEvent) -> None:
        for q in self._subs.get(event.document_id, []):
            q.put_nowait(event)
        for q in self._subs.get("*", []):
            q.put_nowait(event)

    def complete(self, document_id: str) -> None:
        for q in self._subs.get(document_id, []):
            q.put_nowait(None)

    async def stream(self, document_id: str) -> AsyncIterator[IngestionEvent]:
        q = self.subscribe(document_id)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            self.unsubscribe(document_id, q)


event_bus = EventBus()


@dataclass
class IngestionJob:
    document_id: str
    file_path: str
    collection_name: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_api_key: str | None
    chunk_size: int
    chunk_overlap: int
    attempt: int = 0
    max_attempts: int = 3
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def serialize(self) -> bytes:
        return orjson.dumps(
            {
                "document_id": self.document_id,
                "file_path": self.file_path,
                "collection_name": self.collection_name,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
                "embedding_api_key": self.embedding_api_key,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "attempt": self.attempt,
                "max_attempts": self.max_attempts,
                "job_id": self.job_id,
            }
        )

    @classmethod
    def deserialize(cls, data: bytes) -> IngestionJob:
        return cls(**orjson.loads(data))


class IngestionQueue:
    def __init__(self, num_workers: int = 4) -> None:
        self._num_workers = num_workers
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._redis: aioredis.Redis | None = None

    async def connect(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(
            redis_url,
            decode_responses=False,
            max_connections=self._num_workers + 4,
        )
        await self._redis.ping()
        logger.info(f"Queue connected to Redis at {redis_url}")

    async def start(self) -> None:
        self._running = True
        recovered = await self._recover_stuck_jobs()
        if recovered:
            logger.info(f"[queue] recovered {recovered} stuck jobs from previous run")

        for i in range(self._num_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        self._cleanup_task = asyncio.create_task(self._cleanup_old_data())
        logger.info(f"[queue] started {self._num_workers} workers")

    async def stop(self) -> None:
        self._running = False
        if hasattr(self, "_cleanup_task"):
            self._cleanup_task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._redis:
            await self._redis.aclose()
        logger.info("[queue] all workers stopped")

    async def _cleanup_old_data(self) -> None:
        """Periodically clean query_log and webhook_deliveries older than 90 days."""
        from bigrag.database import db

        while True:
            try:
                await asyncio.sleep(86400)  # Run daily
                deleted = await db.execute(
                    "DELETE FROM query_log WHERE created_at < now() - interval '90 days'"
                )
                logger.info(f"query_log cleanup: {deleted}")
                deleted = await db.execute(
                    "DELETE FROM webhook_deliveries WHERE created_at < now() - interval '90 days'"
                )
                logger.info(f"webhook_deliveries cleanup: {deleted}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"Cleanup failed: {e!r}")

    async def _recover_stuck_jobs(self) -> int:
        count = 0
        while True:
            data = await self._redis.lmove(PROCESSING_KEY, QUEUE_KEY, src="RIGHT", dest="LEFT")
            if data is None:
                break
            count += 1
        if count > 0:
            await self._redis.hset(STATS_KEY, "processing", 0)
        return count

    async def enqueue(self, job: IngestionJob) -> None:
        from bigrag.config import settings as _settings

        depth = await self._redis.llen(QUEUE_KEY)
        if depth >= _settings.queue_max_depth:
            raise ValueError("Ingestion queue is full. Try again later.")
        await self._redis.lpush(QUEUE_KEY, job.serialize())
        await self._redis.hincrby(STATS_KEY, "queued", 1)
        pending = await self._redis.llen(QUEUE_KEY)
        logger.info(
            f"[queue] enqueued job={job.job_id} doc={job.document_id} "
            f"collection={job.collection_name} pending={pending}"
        )

    async def flush_collection(self, collection_name: str) -> int:
        """Remove all queued jobs for a collection. Returns count removed."""
        removed = 0
        items = await self._redis.lrange(QUEUE_KEY, 0, -1)
        for item in items:
            try:
                job = IngestionJob.deserialize(item)
                if job.collection_name == collection_name:
                    await self._redis.lrem(QUEUE_KEY, 1, item)
                    removed += 1
            except Exception:
                continue
        if removed:
            logger.info(
                f"[queue] flushed {removed} jobs for collection={collection_name}"
            )
        return removed

    @property
    async def stats(self) -> dict:
        raw = await self._redis.hgetall(STATS_KEY)
        pending = await self._redis.llen(QUEUE_KEY)
        processing = await self._redis.llen(PROCESSING_KEY)
        return {
            "queued": int(raw.get(b"queued", 0)),
            "completed": int(raw.get(b"completed", 0)),
            "failed": int(raw.get(b"failed", 0)),
            "pending": pending,
            "processing": processing,
        }

    async def _worker(self, worker_id: int) -> None:
        logger.info(f"[worker-{worker_id}] started")
        while self._running:
            try:
                data = await self._redis.blmove(
                    QUEUE_KEY, PROCESSING_KEY, timeout=1, src="RIGHT", dest="LEFT"
                )
                if data is None:
                    continue

                job = IngestionJob.deserialize(data)
                try:
                    await self._process_job(worker_id, job)
                finally:
                    await self._redis.lrem(PROCESSING_KEY, 1, data)
            except Exception as e:
                logger.error(f"[worker-{worker_id}] loop error: {e!r}")
                await asyncio.sleep(1)

        logger.info(f"[worker-{worker_id}] stopped")

    def _emit(
        self, doc_id: str, step: str, status: str, msg: str, progress: float = 0.0, **detail
    ) -> None:
        event_bus.publish(
            IngestionEvent(
                document_id=doc_id,
                step=step,
                status=status,
                message=msg,
                progress=progress,
                detail=detail,
            )
        )

    async def _convert_document(self, job: IngestionJob, prefix: str) -> str:
        """Convert document to text via Docling. Returns extracted text."""
        import tempfile

        from bigrag.services.storage import get_storage

        self._emit(
            job.document_id, "converting", "processing", "Parsing document with Docling", 0.15
        )
        t0 = time.monotonic()

        file_data = await get_storage().get(job.file_path)
        suffix = Path(job.file_path).suffix

        def _write_and_convert():
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                tmp.write(file_data)
                tmp.close()
                converter = _get_docling_converter()
                return converter.convert(tmp.name), tmp.name
            except Exception:
                tmp.close()
                raise

        tmp_path = None
        try:
            from bigrag.config import settings as _settings

            result, tmp_path = await asyncio.wait_for(
                asyncio.to_thread(_write_and_convert),
                timeout=_settings.conversion_timeout,
            )
        except TimeoutError:
            from bigrag.config import settings as _settings

            raise ValueError(f"Document conversion timed out after {_settings.conversion_timeout}s")
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        elapsed = time.monotonic() - t0
        logger.info(f"{prefix} docling conversion elapsed={elapsed:.2f}s")
        self._emit(
            job.document_id,
            "converted",
            "processing",
            f"Parsed in {elapsed:.1f}s",
            0.35,
            elapsed=round(elapsed, 2),
        )

        text = result.document.export_to_markdown()
        if not text.strip():
            text = result.document.export_to_text()
        if not text.strip():
            raise ValueError("Document produced no extractable text")

        logger.info(f"{prefix} text extracted chars={len(text)}")
        self._emit(
            job.document_id,
            "text_extracted",
            "processing",
            f"Extracted {len(text):,} characters",
            0.40,
            chars=len(text),
        )
        return text

    async def _chunk_and_embed(self, job: IngestionJob, text: str, prefix: str) -> int:
        """Chunk text, embed, and insert into vector store. Returns total inserted count."""
        from bigrag.config import settings as _settings
        from bigrag.services.embedding import get_embedding_model
        from bigrag.services.ingestion import _chunk_text
        from bigrag.services.vector_store import vector_store

        t0 = time.monotonic()
        embedding_model = get_embedding_model(
            provider=job.embedding_provider,
            model_name=job.embedding_model,
            dimension=job.embedding_dimension,
            api_key=job.embedding_api_key,
        )
        elapsed = time.monotonic() - t0
        logger.info(
            f"{prefix} model loaded provider={job.embedding_provider} "
            f"model={job.embedding_model} elapsed={elapsed:.2f}s"
        )
        self._emit(
            job.document_id,
            "model_loaded",
            "processing",
            f"Loaded {job.embedding_model}",
            0.10,
            provider=job.embedding_provider,
            model=job.embedding_model,
            elapsed=round(elapsed, 2),
        )

        chunks = await asyncio.to_thread(_chunk_text, text, job.chunk_size, job.chunk_overlap)
        if not chunks:
            raise ValueError("Document produced no chunks")
        logger.info(f"{prefix} chunked into {len(chunks)} chunks")
        self._emit(
            job.document_id,
            "chunked",
            "processing",
            f"Split into {len(chunks)} chunks",
            0.45,
            chunks=len(chunks),
            chunk_size=job.chunk_size,
        )

        batch_size = _settings.ingestion_batch_size
        total_inserted = 0
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        doc = job.document_id

        for batch_start in range(0, len(chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_texts = chunks[batch_start:batch_end]
            batch_num = batch_start // batch_size + 1

            t0 = time.monotonic()
            embeddings = await embedding_model.embed(batch_texts)
            embed_elapsed = time.monotonic() - t0

            t1 = time.monotonic()
            ids = [f"{doc}_{i}" for i in range(batch_start, batch_end)]
            doc_ids = [doc] * len(batch_texts)
            indices = list(range(batch_start, batch_end))
            count = await vector_store.insert(
                collection=job.collection_name,
                ids=ids,
                document_ids=doc_ids,
                chunk_indices=indices,
                texts=batch_texts,
                embeddings=embeddings,
            )
            insert_elapsed = time.monotonic() - t1
            total_inserted += count

            progress = 0.45 + (0.45 * batch_num / total_batches)
            logger.info(
                f"{prefix} batch {batch_num}/{total_batches} inserted={count} "
                f"embed={embed_elapsed:.2f}s insert={insert_elapsed:.2f}s"
            )
            self._emit(
                doc,
                "embedding",
                "processing",
                f"Batch {batch_num}/{total_batches} — {total_inserted} vectors",
                progress,
                batch=batch_num,
                total_batches=total_batches,
                inserted=total_inserted,
                embed_time=round(embed_elapsed, 2),
            )

        return total_inserted

    async def _process_job(self, worker_id: int, job: IngestionJob) -> None:
        from bigrag.database import db
        from bigrag.services.vector_store import vector_store

        job.attempt += 1
        prefix = f"[worker-{worker_id}] [job={job.job_id}] [doc={job.document_id}]"
        doc = job.document_id

        await self._redis.hincrby(STATS_KEY, "processing", 1)
        logger.info(f"{prefix} starting attempt={job.attempt}/{job.max_attempts}")
        self._emit(
            doc,
            "queued",
            "processing",
            "Starting ingestion",
            0.0,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
        )

        start_time = time.monotonic()

        try:
            await db.execute(
                "UPDATE documents SET status = 'processing', updated_at = now() WHERE id = $1",
                uuid.UUID(doc),
            )
            self._emit(
                doc,
                "processing",
                "processing",
                "Preparing document",
                0.05,
                collection=job.collection_name,
            )

            text = await self._convert_document(job, prefix)
            total_inserted = await self._chunk_and_embed(job, text, prefix)
            token_count = len(text) // 4  # approximate tokens

            await db.execute(
                "UPDATE documents SET status = 'ready', chunk_count = $1, "
                "token_count = $2, error_message = NULL, updated_at = now() WHERE id = $3",
                total_inserted,
                token_count,
                uuid.UUID(doc),
            )
            await db.execute(
                """UPDATE collections SET
                    document_count = document_count + 1,
                    updated_at = now()
                WHERE name = $1""",
                job.collection_name,
            )

            total_elapsed = time.monotonic() - start_time
            await self._redis.hincrby(STATS_KEY, "completed", 1)
            await self._redis.hincrby(STATS_KEY, "processing", -1)
            logger.info(f"{prefix} complete chunks={total_inserted} elapsed={total_elapsed:.2f}s")
            self._emit(
                doc,
                "complete",
                "complete",
                f"Done — {total_inserted} chunks in {total_elapsed:.1f}s",
                1.0,
                chunks=total_inserted,
                elapsed=round(total_elapsed, 2),
                collection=job.collection_name,
            )
            event_bus.complete(doc)

        except Exception as e:
            total_elapsed = time.monotonic() - start_time
            await self._redis.hincrby(STATS_KEY, "processing", -1)
            logger.error(
                f"{prefix} failed attempt={job.attempt}/{job.max_attempts} "
                f"error={e!r} elapsed={total_elapsed:.2f}s"
            )

            is_permanent = isinstance(e, _PERMANENT_ERRORS)

            if not is_permanent and job.attempt < job.max_attempts:
                try:
                    await vector_store.delete_by_document(job.collection_name, doc)
                except Exception as cleanup_err:
                    logger.warning(f"{prefix} failed to clean up partial vectors: {cleanup_err!r}")

                delay = min(2**job.attempt, 30)
                self._emit(
                    doc,
                    "retrying",
                    "processing",
                    f"Attempt {job.attempt} failed, retrying in {delay}s",
                    0.0,
                    error=str(e),
                    attempt=job.attempt,
                    delay=delay,
                )
                await db.execute(
                    "UPDATE documents SET status = 'pending', "
                    "error_message = $1, updated_at = now() WHERE id = $2",
                    f"Attempt {job.attempt} failed: {e}. Retrying...",
                    uuid.UUID(doc),
                )
                await self.enqueue(job)
            else:
                reason = (
                    "permanent error" if is_permanent else f"{job.max_attempts} attempts exhausted"
                )
                await self._redis.hincrby(STATS_KEY, "failed", 1)
                await self._redis.lpush(DEAD_LETTER_KEY, job.serialize())
                await db.execute(
                    "UPDATE documents SET status = 'failed', "
                    "error_message = $1, updated_at = now() WHERE id = $2",
                    str(e),
                    uuid.UUID(doc),
                )
                logger.error(f"{prefix} permanently failed: {reason}")
                self._emit(
                    doc,
                    "failed",
                    "failed",
                    str(e),
                    0.0,
                    attempts=job.attempt,
                    collection=job.collection_name,
                )
                event_bus.complete(doc)


ingestion_queue = IngestionQueue()
