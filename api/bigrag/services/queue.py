from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.conversion import _get_docling_converter, extract_pdf_text, get_pdf_page_count
from bigrag.services.embedding import truncate_to_tokens
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.ingestion_job import IngestionJob

_EMBEDDING_TIMEOUT_SECONDS = 60


async def _embed_with_cache(
    texts: list[str],
    model,
    provider: str,
    model_name: str,
    dimension: int,
) -> list[list[float]]:

    cache_texts, _ = truncate_to_tokens(texts, model_name)
    logger.info(
        "embedding cache lookup",
        provider=provider,
        model=model_name,
        dimension=dimension,
        inputs=len(texts),
    )
    cached = await embedding_cache.get_many(cache_texts, provider, model_name, dimension)
    missing_idx = [i for i in range(len(texts)) if i not in cached]
    logger.info(
        "embedding cache result",
        provider=provider,
        model=model_name,
        hits=len(texts) - len(missing_idx),
        misses=len(missing_idx),
    )
    if missing_idx:
        missing_by_cache_text: dict[str, int] = {}
        for idx in missing_idx:
            missing_by_cache_text.setdefault(cache_texts[idx], idx)
        provider_idx = list(missing_by_cache_text.values())
        missing_texts = [texts[i] for i in provider_idx]
        missing_cache_texts = [cache_texts[i] for i in provider_idx]
        t0 = time.monotonic()
        logger.info(
            "embedding provider request",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
        )
        fresh = await asyncio.wait_for(
            model.embed(missing_texts),
            timeout=_EMBEDDING_TIMEOUT_SECONDS,
        )
        logger.info(
            "embedding provider response",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
            elapsed=round(time.monotonic() - t0, 2),
        )
        if len(fresh) != len(missing_texts):
            raise ValueError(
                f"embedding provider returned {len(fresh)} vectors for {len(missing_texts)} inputs"
            )
        await embedding_cache.put_many(missing_cache_texts, fresh, provider, model_name, dimension)
        fresh_by_cache_text = dict(zip(missing_cache_texts, fresh, strict=False))
        for idx in missing_idx:
            cached[idx] = fresh_by_cache_text[cache_texts[idx]]
    return [cached[i] for i in range(len(texts))]


logger = get_logger("bigrag.queue")

_PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)

QUEUE_KEY = "bigrag:ingestion:queue"
PROCESSING_KEY = "bigrag:ingestion:processing"
DEAD_LETTER_KEY = "bigrag:ingestion:dead"
STATS_KEY = "bigrag:ingestion:stats"
LEASE_KEY_PREFIX = "bigrag:ingestion:lease:"
COLLECTION_EPOCH_KEY_PREFIX = "bigrag:ingestion:collection_epoch:"
DOCUMENT_EPOCH_KEY_PREFIX = "bigrag:ingestion:document_epoch:"
_LEASE_TTL_SECONDS = 30 * 60
_PDF_OCR_CHUNK_PAGES = 10
_PDF_OCR_PROGRESS_START = 0.16
_PDF_OCR_PROGRESS_END = 0.35


def _docling_result_text(result) -> str:
    text = result.document.export_to_markdown()
    if not text.strip():
        text = result.document.export_to_text()
    return text


def _lease_key(job_id: str) -> str:
    return f"{LEASE_KEY_PREFIX}{job_id}"


def _collection_epoch_key(collection_name: str) -> str:
    return f"{COLLECTION_EPOCH_KEY_PREFIX}{collection_name}"


def _document_epoch_key(document_id: str) -> str:
    return f"{DOCUMENT_EPOCH_KEY_PREFIX}{document_id}"


class IngestionCancelledError(RuntimeError):
    pass


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
        items = await self._redis.lrange(PROCESSING_KEY, 0, -1)
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
                await self._redis.lrem(PROCESSING_KEY, 1, raw)
                continue
            if await self._redis.exists(_lease_key(job.job_id)):
                continue
            await self._redis.lrem(PROCESSING_KEY, 1, raw)
            await self._redis.lpush(QUEUE_KEY, raw)
            recovered += 1
        if recovered > 0:
            await self._redis.hset(STATS_KEY, "processing", 0)
        return recovered

    _ENQUEUE_LUA = """
    local depth = redis.call('LLEN', KEYS[1])
    if depth >= tonumber(ARGV[2]) then
      return -1
    end
    redis.call('LPUSH', KEYS[1], ARGV[1])
    redis.call('HINCRBY', KEYS[2], 'queued', 1)
    return redis.call('LLEN', KEYS[1])
    """

    _FLUSH_LUA = """
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

    async def _epoch_value(self, key: str) -> int:
        if not self._redis:
            return 0
        raw = await self._redis.get(key)
        if raw is None:
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    async def _collection_epoch(self, collection_name: str) -> int:
        return await self._epoch_value(_collection_epoch_key(collection_name))

    async def _document_epoch(self, document_id: str) -> int:
        return await self._epoch_value(_document_epoch_key(document_id))

    async def _ensure_job_current(self, job: IngestionJob) -> None:
        collection_epoch = await self._collection_epoch(job.collection_name)
        if collection_epoch != job.collection_epoch:
            raise IngestionCancelledError(
                f"Ingestion cancelled for collection '{job.collection_name}'"
            )
        document_epoch = await self._document_epoch(job.document_id)
        if document_epoch != job.document_epoch:
            raise IngestionCancelledError(f"Ingestion cancelled for document '{job.document_id}'")

    async def enqueue(self, job: IngestionJob) -> None:
        from bigrag.services.runtime_settings import get_value

        if job.attempt == 0:
            job.collection_epoch = await self._collection_epoch(job.collection_name)
            job.document_epoch = await self._document_epoch(job.document_id)
        queue_max_depth = await get_value("queue_max_depth")
        pending = await self._redis.eval(
            self._ENQUEUE_LUA,
            2,
            QUEUE_KEY,
            STATS_KEY,
            job.serialize(),
            queue_max_depth,
        )
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
        removed = await self._redis.eval(
            self._FLUSH_LUA,
            1,
            QUEUE_KEY,
            collection_name,
        )
        if removed:
            logger.info("queue flushed jobs", collection=collection_name, removed=removed)
        return int(removed)

    async def cancel_collection(self, collection_name: str) -> int:
        if not self._redis:
            return 0
        removed = await self.flush_collection(collection_name)
        await self._redis.incr(_collection_epoch_key(collection_name))
        logger.info("queue cancelled collection jobs", collection=collection_name, flushed=removed)
        return removed

    async def cancel_documents(self, document_ids: list[str]) -> None:
        if not self._redis:
            return
        pipe = self._redis.pipeline(transaction=False)
        for document_id in document_ids:
            pipe.incr(_document_epoch_key(document_id))
        await pipe.execute()
        logger.info("queue cancelled document jobs", count=len(document_ids))

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
        logger.info("worker started", worker_id=worker_id)
        while self._running:
            try:
                data = await self._redis.blmove(
                    QUEUE_KEY, PROCESSING_KEY, timeout=1, src="RIGHT", dest="LEFT"
                )
                if data is None:
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

    _PLAIN_TEXT_EXTS = {".txt", ".csv", ".tsv", ".md", ".json", ".xml"}

    async def _ocr_scanned_pdf(
        self,
        *,
        file_data: bytes,
        suffix: str,
        job: IngestionJob,
        prefix: str,
        start_time: float,
    ) -> str:
        import tempfile

        from bigrag.services.runtime_settings import get_values

        def _write_pdf() -> str:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                tmp.write(file_data)
                tmp.close()
                return tmp.name
            except Exception:
                tmp.close()
                raise

        tmp_path = await asyncio.to_thread(_write_pdf)
        runtime = await get_values(["conversion_timeout"])
        conversion_timeout = runtime["conversion_timeout"]
        current_start = 0
        current_end = 0
        try:
            total_pages = await asyncio.to_thread(get_pdf_page_count, tmp_path)
            if total_pages <= 0:
                raise ValueError("PDF contains no pages")

            chunk_pages = _PDF_OCR_CHUNK_PAGES
            total_chunks = (total_pages + chunk_pages - 1) // chunk_pages
            logger.info(
                "scanned pdf OCR start",
                prefix=prefix,
                pages=total_pages,
                chunk_pages=chunk_pages,
                timeout_per_chunk=conversion_timeout,
            )
            self._emit(
                job.document_id,
                "ocr",
                "processing",
                f"OCRing scanned PDF ({total_pages:,} pages)",
                _PDF_OCR_PROGRESS_START,
                collection_name=job.collection_name,
                pages_total=total_pages,
                chunk_pages=chunk_pages,
            )

            converter = await asyncio.to_thread(_get_docling_converter, pdf_ocr_enabled=True)
            texts: list[str] = []

            for chunk_index, current_start in enumerate(
                range(1, total_pages + 1, chunk_pages),
                start=1,
            ):
                current_end = min(current_start + chunk_pages - 1, total_pages)
                await self._ensure_job_current(job)
                chunk_progress = _PDF_OCR_PROGRESS_START + (
                    (_PDF_OCR_PROGRESS_END - _PDF_OCR_PROGRESS_START)
                    * ((current_start - 1) / total_pages)
                )
                self._emit(
                    job.document_id,
                    "ocr",
                    "processing",
                    f"OCR pages {current_start:,}-{current_end:,} of {total_pages:,}",
                    chunk_progress,
                    collection_name=job.collection_name,
                    page_start=current_start,
                    page_end=current_end,
                    pages_total=total_pages,
                    chunk=chunk_index,
                    total_chunks=total_chunks,
                )

                chunk_start_time = time.monotonic()
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            converter.convert,
                            tmp_path,
                            page_range=(current_start, current_end),
                        ),
                        timeout=conversion_timeout,
                    )
                except TimeoutError as e:
                    raise ValueError(
                        "Scanned PDF OCR timed out while processing "
                        f"pages {current_start}-{current_end} after "
                        f"{conversion_timeout}s"
                    ) from e

                chunk_text = _docling_result_text(result).strip()
                if chunk_text:
                    texts.append(chunk_text)

                elapsed = time.monotonic() - chunk_start_time
                pages_done = current_end
                progress = _PDF_OCR_PROGRESS_START + (
                    (_PDF_OCR_PROGRESS_END - _PDF_OCR_PROGRESS_START) * (pages_done / total_pages)
                )
                logger.info(
                    "scanned pdf OCR chunk complete",
                    prefix=prefix,
                    page_start=current_start,
                    page_end=current_end,
                    pages_total=total_pages,
                    chunk=chunk_index,
                    total_chunks=total_chunks,
                    chars=len(chunk_text),
                    elapsed=round(elapsed, 2),
                )
                self._emit(
                    job.document_id,
                    "ocr",
                    "processing",
                    f"OCRed pages {current_start:,}-{current_end:,} of {total_pages:,}",
                    progress,
                    collection_name=job.collection_name,
                    page_start=current_start,
                    page_end=current_end,
                    pages_done=pages_done,
                    pages_total=total_pages,
                    chunk=chunk_index,
                    total_chunks=total_chunks,
                    chars=len(chunk_text),
                    elapsed=round(elapsed, 2),
                )

            text = "\n\n".join(texts)
            if not text.strip():
                raise ValueError("Document produced no extractable text")

            elapsed = time.monotonic() - start_time
            logger.info(
                "scanned pdf OCR complete",
                prefix=prefix,
                pages_total=total_pages,
                chunks=total_chunks,
                chars=len(text),
                elapsed=round(elapsed, 2),
            )
            self._emit(
                job.document_id,
                "converted",
                "processing",
                f"OCR parsed {total_pages:,} pages in {elapsed:.1f}s",
                _PDF_OCR_PROGRESS_END,
                collection_name=job.collection_name,
                pages_total=total_pages,
                chunks=total_chunks,
                elapsed=round(elapsed, 2),
            )
            self._emit(
                job.document_id,
                "text_extracted",
                "processing",
                f"Extracted {len(text):,} characters",
                0.40,
                collection_name=job.collection_name,
                chars=len(text),
            )
            return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _convert_document(self, job: IngestionJob, prefix: str) -> str:

        import tempfile

        from bigrag.services.runtime_settings import get_values
        from bigrag.services.storage import get_storage

        self._emit(
            job.document_id,
            "converting",
            "processing",
            "Parsing document",
            0.15,
            collection_name=job.collection_name,
        )
        t0 = time.monotonic()

        file_data = await get_storage().get(job.file_path)
        runtime = await get_values(["conversion_timeout", "conversion_pdf_ocr_enabled"])
        conversion_timeout = runtime["conversion_timeout"]
        pdf_ocr_enabled = runtime["conversion_pdf_ocr_enabled"]
        suffix = Path(job.file_path).suffix.lower()
        logger.info(
            "conversion start",
            prefix=prefix,
            collection=job.collection_name,
            file_path=job.file_path,
            suffix=suffix,
            bytes=len(file_data),
        )

        if suffix in self._PLAIN_TEXT_EXTS:
            text = file_data.decode("utf-8", errors="replace")
            if not text.strip():
                raise ValueError("Document produced no extractable text")
            elapsed = time.monotonic() - t0
            logger.info("plain text read", prefix=prefix, elapsed=round(elapsed, 2))
            self._emit(
                job.document_id,
                "text_extracted",
                "processing",
                f"Extracted {len(text):,} characters",
                0.40,
                collection_name=job.collection_name,
                chars=len(text),
            )
            return text

        if suffix == ".pdf":
            tmp_path = None
            logger.info(
                "pdf direct text extraction start",
                prefix=prefix,
                timeout=min(conversion_timeout, 60),
            )

            def _write_and_extract_pdf_text():
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                try:
                    tmp.write(file_data)
                    tmp.close()
                    return extract_pdf_text(tmp.name), tmp.name
                except Exception:
                    tmp.close()
                    raise

            try:
                text, tmp_path = await asyncio.wait_for(
                    asyncio.to_thread(_write_and_extract_pdf_text),
                    timeout=min(conversion_timeout, 60),
                )
            finally:
                if tmp_path:
                    Path(tmp_path).unlink(missing_ok=True)

            if text.strip():
                elapsed = time.monotonic() - t0
                logger.info(
                    "pdf text extracted",
                    prefix=prefix,
                    chars=len(text),
                    elapsed=round(elapsed, 2),
                )
                self._emit(
                    job.document_id,
                    "text_extracted",
                    "processing",
                    f"Extracted {len(text):,} characters",
                    0.40,
                    collection_name=job.collection_name,
                    chars=len(text),
                )
                return text

            if not pdf_ocr_enabled:
                logger.warning(
                    "pdf has no embedded text and OCR is disabled by configuration",
                    prefix=prefix,
                    ocr_enabled=pdf_ocr_enabled,
                )
                raise ValueError(
                    "PDF contains no embedded text and OCR is disabled by configuration. "
                    "Remove the override or set conversion_pdf_ocr_enabled=true."
                )

            return await self._ocr_scanned_pdf(
                file_data=file_data,
                suffix=suffix,
                job=job,
                prefix=prefix,
                start_time=t0,
            )

        def _write_and_convert():
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                tmp.write(file_data)
                tmp.close()
                logger.info(
                    "docling converter start",
                    prefix=prefix,
                    suffix=suffix,
                    timeout=conversion_timeout,
                    pdf_ocr_enabled=pdf_ocr_enabled,
                )
                converter = _get_docling_converter(pdf_ocr_enabled=pdf_ocr_enabled)
                return converter.convert(tmp.name), tmp.name
            except Exception:
                tmp.close()
                raise

        tmp_path = None
        try:
            result, tmp_path = await asyncio.wait_for(
                asyncio.to_thread(_write_and_convert),
                timeout=conversion_timeout,
            )
        except TimeoutError as e:
            raise ValueError(f"Document conversion timed out after {conversion_timeout}s") from e
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        elapsed = time.monotonic() - t0
        logger.info("docling conversion complete", prefix=prefix, elapsed=round(elapsed, 2))
        self._emit(
            job.document_id,
            "converted",
            "processing",
            f"Parsed in {elapsed:.1f}s",
            0.35,
            collection_name=job.collection_name,
            elapsed=round(elapsed, 2),
        )

        text = _docling_result_text(result)
        if not text.strip():
            raise ValueError("Document produced no extractable text")

        logger.info("text extracted", prefix=prefix, chars=len(text))
        self._emit(
            job.document_id,
            "text_extracted",
            "processing",
            f"Extracted {len(text):,} characters",
            0.40,
            collection_name=job.collection_name,
            chars=len(text),
        )
        return text

    async def _chunk_and_embed(self, job: IngestionJob, text: str, prefix: str) -> tuple[int, int]:

        from bigrag.exceptions import ValidationError
        from bigrag.services.collection_config import get_embedding_model_for
        from bigrag.services.ingestion import chunk_document

        vector_store = self._vector_store
        if vector_store is None:
            from bigrag.services.vector_store import vector_store

        t0 = time.monotonic()
        from bigrag.services.collection_cache import get_or_404 as get_collection_or_404

        logger.info("loading collection config", prefix=prefix, collection=job.collection_name)
        collection = await get_collection_or_404(job.collection_name)
        try:
            embedding_model = get_embedding_model_for(collection)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        elapsed = time.monotonic() - t0
        logger.info(
            "model loaded",
            prefix=prefix,
            provider=job.embedding_provider,
            model=job.embedding_model,
            elapsed=round(elapsed, 2),
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
            chunk_document,
            text,
            job.chunk_size,
            job.chunk_overlap,
            strategy,
        )
        if not chunks:
            raise ValueError("Document produced no chunks")
        logger.info("document chunked", prefix=prefix, chunks=len(chunks), strategy=strategy)
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

        await self._ensure_job_current(job)
        logger.info(
            "ensuring vector collection",
            prefix=prefix,
            collection=job.collection_name,
            dimension=job.embedding_dimension,
        )
        await vector_store.create_collection(
            job.collection_name,
            job.embedding_dimension,
            tenant_field=getattr(job, "tenant_field", None),
        )
        await self._ensure_job_current(job)

        from bigrag.services.runtime_settings import get_value

        batch_size = await get_value("ingestion_batch_size")
        total_inserted = 0
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        doc = job.document_id

        max_batch_retries = 3
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
                    logger.info(
                        "batch embedding start",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        chunks=len(batch_texts),
                        attempt=attempt,
                    )
                    embeddings = await _embed_with_cache(
                        batch_texts,
                        embedding_model,
                        job.embedding_provider,
                        job.embedding_model,
                        job.embedding_dimension,
                    )
                    embed_elapsed = time.monotonic() - t0

                    t1 = time.monotonic()
                    await self._ensure_job_current(job)
                    ids = [f"{doc}_{i}" for i in range(batch_start, batch_end)]
                    doc_ids = [doc] * len(batch_texts)
                    indices = list(range(batch_start, batch_end))
                    metadata = [
                        {"char_start": c.char_start, "char_end": c.char_end} for c in batch_chunks
                    ]
                    logger.info(
                        "batch vector insert start",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        chunks=len(batch_texts),
                    )
                    count = await vector_store.insert(
                        collection=job.collection_name,
                        ids=ids,
                        document_ids=doc_ids,
                        chunk_indices=indices,
                        texts=batch_texts,
                        embeddings=embeddings,
                        metadata=metadata,
                    )
                    try:
                        await self._ensure_job_current(job)
                    except IngestionCancelledError:
                        await vector_store.delete_by_document(job.collection_name, doc)
                        raise
                    insert_elapsed = time.monotonic() - t1
                    break
                except _PERMANENT_ERRORS:
                    raise
                except Exception as exc:
                    if attempt >= max_batch_retries:
                        logger.error(
                            "batch exhausted retries",
                            prefix=prefix,
                            batch=batch_num,
                            total_batches=total_batches,
                            chunks=len(batch_texts),
                            error=repr(exc),
                        )
                        count = 0
                        break
                    delay = batch_backoff_base**attempt
                    logger.warning(
                        "batch attempt failed",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        attempt=attempt,
                        max_attempts=max_batch_retries,
                        error=repr(exc),
                        retrying_in=delay,
                    )
                    await asyncio.sleep(delay)
            total_inserted += count

            progress = 0.45 + (0.45 * batch_num / total_batches)
            logger.info(
                "batch inserted",
                prefix=prefix,
                batch=batch_num,
                total_batches=total_batches,
                inserted=count,
                embed_elapsed=round(embed_elapsed, 2),
                insert_elapsed=round(insert_elapsed, 2),
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

        return total_inserted, len(chunks)

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
                try:
                    await vector_store.delete_by_document(job.collection_name, doc)
                except Exception as cleanup_err:
                    logger.warning(
                        "failed to clean up cancelled vectors",
                        prefix=prefix,
                        error=repr(cleanup_err),
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
                try:
                    await vector_store.delete_by_document(job.collection_name, doc)
                except Exception as cleanup_err:
                    logger.warning(
                        "failed to clean up partial vectors",
                        prefix=prefix,
                        error=repr(cleanup_err),
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
