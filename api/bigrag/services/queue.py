from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.conversion import _get_docling_converter
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.ingestion_job import IngestionJob


async def _embed_with_cache(
    texts: list[str],
    model,
    provider: str,
    model_name: str,
    dimension: int,
) -> list[list[float]]:
    """Fetch vectors from the persistent cache, embed the misses, and
    write them back. Returns vectors aligned to the input order."""
    cached = await embedding_cache.get_many(texts, provider, model_name, dimension)
    missing_idx = [i for i in range(len(texts)) if i not in cached]
    if missing_idx:
        missing_texts = [texts[i] for i in missing_idx]
        fresh = await model.embed(missing_texts)
        if len(fresh) != len(missing_texts):
            raise ValueError(
                f"embedding provider returned {len(fresh)} vectors for "
                f"{len(missing_texts)} inputs"
            )
        await embedding_cache.put_many(missing_texts, fresh, provider, model_name, dimension)
        for idx, vec in zip(missing_idx, fresh, strict=False):
            cached[idx] = vec
    return [cached[i] for i in range(len(texts))]

logger = get_logger("bigrag.queue")

_PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)

QUEUE_KEY = "bigrag:ingestion:queue"
PROCESSING_KEY = "bigrag:ingestion:processing"
DEAD_LETTER_KEY = "bigrag:ingestion:dead"
STATS_KEY = "bigrag:ingestion:stats"


class IngestionQueue:
    def __init__(self, num_workers: int = 4) -> None:
        self._num_workers = num_workers
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._redis: aioredis.Redis | None = None
        self._db = None
        self._vector_store = None

    async def connect(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(
            redis_url,
            decode_responses=False,
            max_connections=self._num_workers + 4,
        )
        await self._redis.ping()
        logger.info(f"Queue connected to Redis at {redis_url}")

    async def start(self, db=None, vector_store=None) -> None:
        if db is not None:
            self._db = db
        if vector_store is not None:
            self._vector_store = vector_store

        self._running = True
        recovered = await self._recover_stuck_jobs()
        if recovered:
            logger.info(f"[queue] recovered {recovered} stuck jobs from previous run")

        for i in range(self._num_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        logger.info(f"[queue] started {self._num_workers} workers")

    async def stop(self) -> None:
        self._running = False
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._redis:
            await self._redis.aclose()
        logger.info("[queue] all workers stopped")

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
        if not self._redis:
            return 0
        removed = 0
        items = await self._redis.lrange(QUEUE_KEY, 0, -1)
        for item in items:
            try:
                job = IngestionJob.deserialize(item)
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning(
                    "queue: malformed job payload, skipping",
                    error=f"{exc.__class__.__name__}: {exc}",
                )
                continue
            if job.collection_name == collection_name:
                await self._redis.lrem(QUEUE_KEY, 1, item)
                removed += 1
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
        self,
        doc_id: str,
        step: str,
        status: str,
        msg: str,
        progress: float = 0.0,
        collection_name: str = "",
        **detail,
    ) -> None:
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

    _PLAIN_TEXT_EXTS = {".txt", ".csv", ".tsv", ".md", ".json", ".xml"}

    async def _convert_document(self, job: IngestionJob, prefix: str) -> str:
        """Convert document to text via Docling (or read directly for plain text)."""
        import tempfile

        from bigrag.services.storage import get_storage

        self._emit(
            job.document_id, "converting", "processing", "Parsing document", 0.15,
            collection_name=job.collection_name,
        )
        t0 = time.monotonic()

        file_data = await get_storage().get(job.file_path)
        suffix = Path(job.file_path).suffix.lower()

        # Plain text formats: skip Docling, use content directly
        if suffix in self._PLAIN_TEXT_EXTS:
            text = file_data.decode("utf-8", errors="replace")
            if not text.strip():
                raise ValueError("Document produced no extractable text")
            elapsed = time.monotonic() - t0
            logger.info(f"{prefix} plain text read elapsed={elapsed:.2f}s")
            self._emit(
                job.document_id, "text_extracted", "processing",
                f"Extracted {len(text):,} characters", 0.40,
                collection_name=job.collection_name, chars=len(text),
            )
            return text

        # All other formats: use Docling
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
        except TimeoutError as e:
            from bigrag.config import settings as _settings

            raise ValueError(
                f"Document conversion timed out after {_settings.conversion_timeout}s"
            ) from e
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        elapsed = time.monotonic() - t0
        logger.info(f"{prefix} docling conversion elapsed={elapsed:.2f}s")
        self._emit(
            job.document_id, "converted", "processing",
            f"Parsed in {elapsed:.1f}s", 0.35,
            collection_name=job.collection_name, elapsed=round(elapsed, 2),
        )

        text = result.document.export_to_markdown()
        if not text.strip():
            text = result.document.export_to_text()
        if not text.strip():
            raise ValueError("Document produced no extractable text")

        logger.info(f"{prefix} text extracted chars={len(text)}")
        self._emit(
            job.document_id, "text_extracted", "processing",
            f"Extracted {len(text):,} characters", 0.40,
            collection_name=job.collection_name, chars=len(text),
        )
        return text

    async def _chunk_and_embed(self, job: IngestionJob, text: str, prefix: str) -> int:
        """Chunk text, embed, and insert into vector store. Returns total inserted count."""
        from bigrag.config import settings as _settings
        from bigrag.services.embedding import get_embedding_model
        from bigrag.services.ingestion import chunk_document

        vector_store = self._vector_store
        if vector_store is None:
            from bigrag.services.vector_store import vector_store

        t0 = time.monotonic()
        embedding_model = get_embedding_model(
            provider=job.embedding_provider,
            model_name=job.embedding_model,
            dimension=job.embedding_dimension,
            api_key=job.embedding_api_key,
            base_url=getattr(job, "embedding_base_url", None),
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
            collection_name=job.collection_name,
            provider=job.embedding_provider,
            model=job.embedding_model,
            elapsed=round(elapsed, 2),
        )

        strategy = getattr(job, "chunk_strategy", "paragraph") or "paragraph"
        chunks = await asyncio.to_thread(
            chunk_document, text, job.chunk_size, job.chunk_overlap, strategy,
        )
        if not chunks:
            raise ValueError("Document produced no chunks")
        logger.info(
            f"{prefix} chunked into {len(chunks)} chunks (strategy={strategy})"
        )
        self._emit(
            job.document_id,
            "chunked",
            "processing",
            f"Split into {len(chunks)} chunks",
            0.45,
            collection_name=job.collection_name,
            chunks=len(chunks),
            chunk_size=job.chunk_size,
        )

        # Ensure Milvus collection exists (may have been dropped by truncate or
        # missed during creation if Milvus was unavailable)
        await vector_store.create_collection(job.collection_name, job.embedding_dimension)

        batch_size = _settings.ingestion_batch_size
        total_inserted = 0
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        doc = job.document_id

        # P1-I4: chunk-level retry. A flaky embedding call or a single
        # oversized chunk in the middle of a large doc used to fail the
        # whole document. We now retry each batch up to MAX_BATCH_RETRIES
        # with exponential backoff; on exhaustion the batch's chunks are
        # skipped (logged) and the doc still completes for whatever did
        # embed — better than hours of re-ingest because one chunk was
        # bad.
        MAX_BATCH_RETRIES = 3
        batch_backoff_base = 2

        for batch_start in range(0, len(chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_chunks = chunks[batch_start:batch_end]
            batch_texts = [c.text for c in batch_chunks]
            batch_num = batch_start // batch_size + 1

            embed_elapsed = 0.0
            insert_elapsed = 0.0
            count = 0
            attempt = 0
            while True:
                attempt += 1
                try:
                    t0 = time.monotonic()
                    embeddings = await _embed_with_cache(
                        batch_texts,
                        embedding_model,
                        job.embedding_provider,
                        job.embedding_model,
                        job.embedding_dimension,
                    )
                    embed_elapsed = time.monotonic() - t0

                    t1 = time.monotonic()
                    ids = [f"{doc}_{i}" for i in range(batch_start, batch_end)]
                    doc_ids = [doc] * len(batch_texts)
                    indices = list(range(batch_start, batch_end))
                    metadata = [
                        {"char_start": c.char_start, "char_end": c.char_end}
                        for c in batch_chunks
                    ]
                    count = await vector_store.insert(
                        collection=job.collection_name,
                        ids=ids,
                        document_ids=doc_ids,
                        chunk_indices=indices,
                        texts=batch_texts,
                        embeddings=embeddings,
                        metadata=metadata,
                    )
                    insert_elapsed = time.monotonic() - t1
                    break
                except _PERMANENT_ERRORS:
                    raise
                except Exception as exc:  # noqa: BLE001 — retry on anything transient
                    if attempt >= MAX_BATCH_RETRIES:
                        logger.error(
                            f"{prefix} batch {batch_num}/{total_batches} exhausted "
                            f"retries, skipping {len(batch_texts)} chunks: {exc!r}"
                        )
                        count = 0
                        break
                    delay = batch_backoff_base**attempt
                    logger.warning(
                        f"{prefix} batch {batch_num}/{total_batches} attempt "
                        f"{attempt}/{MAX_BATCH_RETRIES} failed ({exc!r}), "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
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
                collection_name=job.collection_name,
                batch=batch_num,
                total_batches=total_batches,
                inserted=total_inserted,
                embed_time=round(embed_elapsed, 2),
            )

        return total_inserted

    async def _process_job(self, worker_id: int, job: IngestionJob) -> None:
        db = self._db
        if db is None:
            from bigrag.database import db

        vector_store = self._vector_store
        if vector_store is None:
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
            collection_name=job.collection_name,
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
                collection_name=job.collection_name,
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
                collection_name=job.collection_name,
                chunks=total_inserted,
                elapsed=round(total_elapsed, 2),
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
                    collection_name=job.collection_name,
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
                await self._redis.ltrim(DEAD_LETTER_KEY, 0, 999)  # cap at 1000
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
                    collection_name=job.collection_name,
                    attempts=job.attempt,
                )
                event_bus.complete(doc)


# Keep backward-compatible module-level singleton for imports that haven't migrated
ingestion_queue = IngestionQueue()
