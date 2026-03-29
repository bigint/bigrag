from __future__ import annotations

import logging

from bigrag.services.embedding import EmbeddingModel
from bigrag.services.vector_store import vector_store

logger = logging.getLogger("bigrag.retrieval")


async def retrieve(
    collection_name: str,
    query: str,
    embedding_model: EmbeddingModel,
    top_k: int = 10,
    filters: dict | None = None,
    min_score: float | None = None,
) -> list[dict]:
    """Embed query and search Milvus for similar chunks."""
    # Embed the query
    embeddings = await embedding_model.embed([query])
    query_embedding = embeddings[0]

    # Build Milvus filter expression
    filter_expr = _build_filter_expr(filters) if filters else None

    # Search
    results = await vector_store.search(
        collection=collection_name,
        query_embedding=query_embedding,
        top_k=top_k,
        filters=filter_expr,
    )

    # Apply minimum score filter
    if min_score is not None:
        results = [r for r in results if r["score"] >= min_score]

    return results


def _build_filter_expr(filters: dict) -> str | None:
    """Convert filter dict to Milvus filter expression."""
    expressions = []

    for key, value in filters.items():
        if isinstance(value, str):
            expressions.append(f'{key} == "{value}"')
        elif isinstance(value, (int, float)):
            expressions.append(f"{key} == {value}")
        elif isinstance(value, dict):
            for op, val in value.items():
                if op == "$eq":
                    if isinstance(val, str):
                        expressions.append(f'{key} == "{val}"')
                    else:
                        expressions.append(f"{key} == {val}")
                elif op == "$ne":
                    if isinstance(val, str):
                        expressions.append(f'{key} != "{val}"')
                    else:
                        expressions.append(f"{key} != {val}")
                elif op == "$gt":
                    expressions.append(f"{key} > {val}")
                elif op == "$gte":
                    expressions.append(f"{key} >= {val}")
                elif op == "$lt":
                    expressions.append(f"{key} < {val}")
                elif op == "$lte":
                    expressions.append(f"{key} <= {val}")
                elif op == "$in":
                    vals = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in val)
                    expressions.append(f"{key} in [{vals}]")

    return " and ".join(expressions) if expressions else None
