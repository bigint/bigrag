from __future__ import annotations

import asyncio

from bigrag.models.query import BatchQueryItem, BatchQueryResultItem, QueryResult
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_reranking_config
from bigrag.services.retrieval.embedding import resolve_embedding_model
from bigrag.services.retrieval.orchestrate import retrieve
from bigrag.services.retrieval.result_shaping import (
    result_to_dict,
    results_with_document_filenames,
)
from bigrag.services.tenant_enforcement import enforce_tenant_filters

FANOUT_LIMIT = 8


async def run_batch_query(
    queries: list[BatchQueryItem],
    principal: dict,
) -> list[BatchQueryResultItem]:
    batch_semaphore = asyncio.Semaphore(FANOUT_LIMIT)

    async def run_one(item: BatchQueryItem) -> tuple[BatchQueryItem, list[dict], int, bool]:
        async with batch_semaphore:
            collection = await get_collection_or_404(item.collection)
            item_filters = enforce_tenant_filters(collection, item.filters, principal)
            embedding_model = resolve_embedding_model(
                collection,
                error_label=f"Collection '{item.collection}'",
            )

            outcome = await retrieve(
                collection_name=item.collection,
                query=item.query,
                embedding_model=embedding_model,
                top_k=item.top_k,
                filters=item_filters,
                min_score=item.min_score,
                search_mode=item.search_mode,
                reranking_config=get_reranking_config(collection),
                rerank_override=item.rerank,
                skip_cache=item.skip_cache,
            )

            include_multimodal = bool(item.multimodal and collection.get("multimodal_enabled"))
            return item, outcome.results, len(outcome.results), include_multimodal

    raw_results = await asyncio.gather(*[run_one(item) for item in queries])
    flat_rows = []
    row_counts = []
    for _, rows, _, _ in raw_results:
        row_counts.append(len(rows))
        flat_rows.extend(rows)
    enriched_rows = await results_with_document_filenames(flat_rows)
    results = []
    cursor = 0
    for (item, _, total, include_multimodal), row_count in zip(
        raw_results,
        row_counts,
        strict=True,
    ):
        rows = enriched_rows[cursor : cursor + row_count]
        cursor += row_count
        results.append(
            BatchQueryResultItem(
                results=[
                    QueryResult(**result_to_dict(r, include_multimodal=include_multimodal))
                    for r in rows
                ],
                query=item.query,
                collection=item.collection,
                total=total,
            )
        )
    return results
