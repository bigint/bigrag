"""Background ingestion queue with worker pool, SSE event bus, and structured logging."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator

logger = logging.getLogger("bigrag.queue")


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


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
        return f"data: {json.dumps(data)}\n\n"


class EventBus:
    """Pub/sub for ingestion progress events. Subscribers get events for specific document IDs."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[IngestionEvent | None]]] = {}

    def subscribe(self, document_id: str) -> asyncio.Queue[IngestionEvent | None]:
        q: asyncio.Queue[IngestionEvent | None] = asyncio.Queue()
        self._subscribers.setdefault(document_id, []).append(q)
        return q

    def unsubscribe(self, document_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(document_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subscribers.pop(document_id, None)

    def publish(self, event: IngestionEvent) -> None:
        for q in self._subscribers.get(event.document_id, []):
            q.put_nowait(event)
        # Also publish to wildcard subscribers (for global feed)
        for q in self._subscribers.get("*", []):
            q.put_nowait(event)

    def complete(self, document_id: str) -> None:
        for q in self._subscribers.get(document_id, []):
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
    embedding_base_url: str | None
    chunk_size: int
    chunk_overlap: int
    attempt: int = 0
    max_attempts: int = 3
    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class IngestionQueue:
    def __init__(self, num_workers: int = 2) -> None:
        self._queue: asyncio.Queue[IngestionJob] = asyncio.Queue()
        self._num_workers = num_workers
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._stats = {"queued": 0, "processing": 0, "completed": 0, "failed": 0}

    @property
    def stats(self) -> dict:
        return {**self._stats, "pending": self._queue.qsize()}

    async def start(self) -> None:
        self._running = True
        for i in range(self._num_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        logger.info(f"[queue] started {self._num_workers} ingestion workers")

    async def stop(self) -> None:
        self._running = False
        for _ in self._workers:
            await self._queue.put(None)  # type: ignore[arg-type]
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("[queue] all workers stopped")

    def enqueue(self, job: IngestionJob) -> None:
        self._queue.put_nowait(job)
        self._stats["queued"] += 1
        logger.info(
            f"[queue] enqueued job={job.job_id} doc={job.document_id} "
            f"collection={job.collection_name} file={job.file_path} "
            f"pending={self._queue.qsize()}"
        )

    async def _worker(self, worker_id: int) -> None:
        logger.info(f"[worker-{worker_id}] started")
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if job is None:
                break

            await self._process_job(worker_id, job)
            self._queue.task_done()

        logger.info(f"[worker-{worker_id}] stopped")

    def _emit(self, doc_id: str, step: str, status: str, msg: str, progress: float = 0.0, **detail) -> None:
        event_bus.publish(IngestionEvent(
            document_id=doc_id, step=step, status=status,
            message=msg, progress=progress, detail=detail,
        ))

    async def _process_job(self, worker_id: int, job: IngestionJob) -> None:
        from bigrag.database import db
        from bigrag.services.embedding import get_embedding_model
        from bigrag.services.vector_store import vector_store

        job.attempt += 1
        prefix = f"[worker-{worker_id}] [job={job.job_id}] [doc={job.document_id}]"
        doc = job.document_id
        self._stats["processing"] += 1

        logger.info(f"{prefix} starting ingestion attempt={job.attempt}/{job.max_attempts}")
        self._emit(doc, "queued", "processing", "Starting ingestion", 0.0,
                   attempt=job.attempt, max_attempts=job.max_attempts)

        start_time = time.monotonic()

        try:
            # Step 1: Update status to processing
            await db.execute(
                "UPDATE documents SET status = 'processing', updated_at = now() WHERE id = $1",
                uuid.UUID(doc),
            )
            logger.info(f"{prefix} status=processing")
            self._emit(doc, "processing", "processing", "Preparing document", 0.05)

            # Step 2: Load embedding model
            t0 = time.monotonic()
            embedding_model = get_embedding_model(
                provider=job.embedding_provider,
                model_name=job.embedding_model,
                dimension=job.embedding_dimension,
                api_key=job.embedding_api_key,
                base_url=job.embedding_base_url,
            )
            elapsed = time.monotonic() - t0
            logger.info(f"{prefix} embedding model loaded provider={job.embedding_provider} model={job.embedding_model} elapsed={elapsed:.2f}s")
            self._emit(doc, "model_loaded", "processing",
                       f"Loaded {job.embedding_model}", 0.10,
                       provider=job.embedding_provider, model=job.embedding_model, elapsed=round(elapsed, 2))

            # Step 3: Convert document with Docling
            self._emit(doc, "converting", "processing", "Parsing document with Docling", 0.15)
            t0 = time.monotonic()
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(job.file_path)
            elapsed = time.monotonic() - t0
            logger.info(f"{prefix} docling conversion complete elapsed={elapsed:.2f}s")
            self._emit(doc, "converted", "processing",
                       f"Document parsed in {elapsed:.1f}s", 0.35, elapsed=round(elapsed, 2))

            # Step 4: Extract text
            t0 = time.monotonic()
            text = result.document.export_to_markdown()
            if not text.strip():
                text = result.document.export_to_text()
            if not text.strip():
                raise ValueError("Document produced no extractable text")
            text_len = len(text)
            elapsed = time.monotonic() - t0
            logger.info(f"{prefix} text extracted chars={text_len} elapsed={elapsed:.2f}s")
            self._emit(doc, "text_extracted", "processing",
                       f"Extracted {text_len:,} characters", 0.40, chars=text_len)

            # Step 5: Chunk
            t0 = time.monotonic()
            from bigrag.services.ingestion import _chunk_text
            chunks = _chunk_text(text, job.chunk_size, job.chunk_overlap)
            if not chunks:
                raise ValueError("Document produced no chunks after processing")
            elapsed = time.monotonic() - t0
            logger.info(f"{prefix} chunking complete chunks={len(chunks)} chunk_size={job.chunk_size} overlap={job.chunk_overlap} elapsed={elapsed:.2f}s")
            self._emit(doc, "chunked", "processing",
                       f"Split into {len(chunks)} chunks", 0.45,
                       chunks=len(chunks), chunk_size=job.chunk_size)

            # Step 6: Embed and insert in batches
            batch_size = 64
            total_inserted = 0
            total_batches = (len(chunks) + batch_size - 1) // batch_size

            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch_texts = chunks[batch_start:batch_end]
                batch_num = batch_start // batch_size + 1

                # Embed
                t0 = time.monotonic()
                embeddings = await embedding_model.embed(batch_texts)
                embed_elapsed = time.monotonic() - t0

                # Insert into Milvus
                t1 = time.monotonic()
                ids = [f"{doc}_{i}" for i in range(batch_start, batch_end)]
                doc_ids = [doc] * len(batch_texts)
                indices = list(range(batch_start, batch_end))

                count = vector_store.insert(
                    collection=job.collection_name,
                    ids=ids, document_ids=doc_ids, chunk_indices=indices,
                    texts=batch_texts, embeddings=embeddings,
                )
                insert_elapsed = time.monotonic() - t1
                total_inserted += count

                # Progress: 0.45 to 0.90 for embedding phase
                batch_progress = 0.45 + (0.45 * batch_num / total_batches)

                logger.info(f"{prefix} batch {batch_num}/{total_batches} chunks={len(batch_texts)} inserted={count} embed={embed_elapsed:.2f}s insert={insert_elapsed:.2f}s")
                self._emit(doc, "embedding", "processing",
                           f"Batch {batch_num}/{total_batches} — {total_inserted} vectors stored",
                           batch_progress,
                           batch=batch_num, total_batches=total_batches,
                           inserted=total_inserted, embed_time=round(embed_elapsed, 2))

            # Step 7: Mark as ready
            await db.execute(
                "UPDATE documents SET status = 'ready', chunk_count = $1, error_message = NULL, updated_at = now() WHERE id = $2",
                total_inserted, uuid.UUID(doc),
            )
            await db.execute(
                """
                UPDATE collections SET
                    document_count = (SELECT COUNT(*) FROM documents WHERE collection_id = collections.id AND status = 'ready'),
                    updated_at = now()
                WHERE name = $1
                """,
                job.collection_name,
            )

            total_elapsed = time.monotonic() - start_time
            self._stats["completed"] += 1
            self._stats["processing"] -= 1
            logger.info(f"{prefix} ingestion complete chunks={total_inserted} total_elapsed={total_elapsed:.2f}s")
            self._emit(doc, "complete", "complete",
                       f"Done — {total_inserted} chunks in {total_elapsed:.1f}s", 1.0,
                       chunks=total_inserted, elapsed=round(total_elapsed, 2))
            event_bus.complete(doc)

        except Exception as e:
            total_elapsed = time.monotonic() - start_time
            self._stats["processing"] -= 1

            logger.error(f"{prefix} ingestion failed attempt={job.attempt}/{job.max_attempts} error={e!r} elapsed={total_elapsed:.2f}s")

            if job.attempt < job.max_attempts:
                delay = 2 ** job.attempt
                logger.info(f"{prefix} retrying in {delay}s")
                self._emit(doc, "retrying", "processing",
                           f"Attempt {job.attempt} failed, retrying in {delay}s",
                           0.0, error=str(e), attempt=job.attempt, delay=delay)
                await db.execute(
                    "UPDATE documents SET status = 'pending', error_message = $1, updated_at = now() WHERE id = $2",
                    f"Attempt {job.attempt} failed: {e}. Retrying...", uuid.UUID(doc),
                )
                await asyncio.sleep(delay)
                self.enqueue(job)
            else:
                self._stats["failed"] += 1
                await db.execute(
                    "UPDATE documents SET status = 'failed', error_message = $1, updated_at = now() WHERE id = $2",
                    str(e), uuid.UUID(doc),
                )
                logger.error(f"{prefix} permanently failed after {job.max_attempts} attempts")
                self._emit(doc, "failed", "failed",
                           str(e), 0.0, attempts=job.max_attempts)
                event_bus.complete(doc)


ingestion_queue = IngestionQueue()
