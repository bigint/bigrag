from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from bigrag.logging import get_logger
from bigrag.services.document_elements import ParsedDocument
from bigrag.services.embedding_rate_limit import rate_limit_cooldown_key
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")


@dataclass
class EmbedPlan:
    collection: object
    embedding_model: object
    cooldown_key: str
    text: str
    elements: list
    include_elements: bool
    chunks: list
    batches: list[tuple[int, int, int, list]]
    batch_size: int
    total_batches: int


async def build_plan(
    job: IngestionJob,
    parsed: ParsedDocument | str,
    prefix: str,
    *,
    vector_store,
    emit,
    ensure_job_current,
) -> EmbedPlan:
    from bigrag.exceptions import ValidationError
    from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
    from bigrag.services.collection_config import get_embedding_model_for
    from bigrag.services.conversion import MAX_EXTRACTED_TEXT_CHARS
    from bigrag.services.ingestion import chunk_document
    from bigrag.services.runtime_settings import get_value

    text = parsed.text if isinstance(parsed, ParsedDocument) else parsed
    elements = parsed.elements if isinstance(parsed, ParsedDocument) else []
    include_elements = job.multimodal_enabled or job.multimodal_enrichment_enabled
    t0 = time.monotonic()
    logger.debug("loading collection config", prefix=prefix, collection=job.collection_name)
    collection = await get_collection_or_404(job.collection_name)
    try:
        embedding_model = get_embedding_model_for(collection)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    elapsed = time.monotonic() - t0
    logger.debug(
        "model loaded",
        prefix=prefix,
        provider=job.embedding_provider,
        model=job.embedding_model,
        elapsed=round(elapsed, 2),
    )
    cooldown_key = rate_limit_cooldown_key(
        embedding_model,
        job.embedding_provider,
        job.embedding_model,
        job.embedding_dimension,
    )
    emit(
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

    if len(text) > MAX_EXTRACTED_TEXT_CHARS:
        raise ValueError(
            f"Extracted text length {len(text)} exceeds the maximum of "
            f"{MAX_EXTRACTED_TEXT_CHARS} characters"
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
    logger.debug("document chunked", prefix=prefix, chunks=len(chunks), strategy=strategy)
    emit(
        job.document_id,
        "chunked",
        "processing",
        f"Split into {len(chunks)} chunks",
        0.45,
        collection_name=job.collection_name,
        chunks=len(chunks),
        chunk_size=job.chunk_size,
    )

    await ensure_job_current(job)
    logger.debug(
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
    await ensure_job_current(job)

    batch_size = await get_value("ingestion_batch_size")
    total_batches = (len(chunks) + batch_size - 1) // batch_size

    batches: list[tuple[int, int, int, list]] = []
    for batch_start in range(0, len(chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(chunks))
        batch_num = batch_start // batch_size + 1
        batches.append((batch_num, batch_start, batch_end, chunks[batch_start:batch_end]))

    return EmbedPlan(
        collection=collection,
        embedding_model=embedding_model,
        cooldown_key=cooldown_key,
        text=text,
        elements=elements,
        include_elements=include_elements,
        chunks=chunks,
        batches=batches,
        batch_size=batch_size,
        total_batches=total_batches,
    )
