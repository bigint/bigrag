from __future__ import annotations

from bigrag.services.document_elements import ParsedDocument
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_embedding.embed_batches import embed_all_batches
from bigrag.services.queue_embedding.insert_batches import insert_all_batches
from bigrag.services.queue_embedding.plan import build_plan


async def chunk_and_embed(
    job: IngestionJob,
    parsed: ParsedDocument | str,
    prefix: str,
    *,
    vector_store,
    emit,
    ensure_job_current,
) -> tuple[int, int]:
    if vector_store is None:
        from bigrag.services.vector_store import vector_store

    plan = await build_plan(
        job,
        parsed,
        prefix,
        vector_store=vector_store,
        emit=emit,
        ensure_job_current=ensure_job_current,
    )

    embed_results = await embed_all_batches(
        job,
        prefix,
        embedding_model=plan.embedding_model,
        cooldown_key=plan.cooldown_key,
        batches=plan.batches,
        total_batches=plan.total_batches,
    )

    total_inserted = await insert_all_batches(
        job,
        prefix,
        vector_store=vector_store,
        emit=emit,
        ensure_job_current=ensure_job_current,
        embed_results=embed_results,
        elements=plan.elements,
        include_elements=plan.include_elements,
        total_batches=plan.total_batches,
    )

    return total_inserted, len(plan.chunks)
