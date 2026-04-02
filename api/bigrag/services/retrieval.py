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
    import time

    # Embed the query
    t0 = time.monotonic()
    embeddings = await embedding_model.embed([query], input_type="query")
    query_embedding = embeddings[0]
    embed_ms = (time.monotonic() - t0) * 1000
    logger.info(f"retrieve: embedded query collection={collection_name} model={embedding_model.name} {embed_ms:.0f}ms")

    # Build Milvus filter expression
    filter_expr = _build_filter_expr(filters) if filters else None

    # Search
    t0 = time.monotonic()
    results = await vector_store.search(
        collection=collection_name,
        query_embedding=query_embedding,
        top_k=top_k,
        filters=filter_expr,
    )
    search_ms = (time.monotonic() - t0) * 1000
    logger.info(f"retrieve: searched collection={collection_name} hits={len(results)} top_k={top_k} {search_ms:.0f}ms")

    # Apply minimum score filter
    if min_score is not None:
        before = len(results)
        results = [r for r in results if r["score"] >= min_score]
        logger.info(f"retrieve: score filter min={min_score} before={before} after={len(results)}")

    return results


import re

_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_ALLOWED_FIELDS = {"document_id", "chunk_index", "text"}


def _validate_field(key: str) -> str:
    """Validate that a field name is safe for use in filter expressions."""
    if not _SAFE_FIELD_RE.match(key):
        raise ValueError(f"Invalid filter field name: {key!r}")
    return key


def _escape_string(value: str) -> str:
    """Escape a string value for safe use in Milvus filter expressions."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_filter_expr(filters: dict) -> str | None:
    """Convert filter dict to Milvus filter expression."""
    expressions = []

    for key, value in filters.items():
        field = _validate_field(key)
        if isinstance(value, str):
            expressions.append(f'{field} == "{_escape_string(value)}"')
        elif isinstance(value, (int, float)):
            expressions.append(f"{field} == {value}")
        elif isinstance(value, dict):
            for op, val in value.items():
                if op == "$eq":
                    if isinstance(val, str):
                        expressions.append(f'{field} == "{_escape_string(val)}"')
                    else:
                        expressions.append(f"{field} == {val}")
                elif op == "$ne":
                    if isinstance(val, str):
                        expressions.append(f'{field} != "{_escape_string(val)}"')
                    else:
                        expressions.append(f"{field} != {val}")
                elif op == "$gt":
                    expressions.append(f"{field} > {val}")
                elif op == "$gte":
                    expressions.append(f"{field} >= {val}")
                elif op == "$lt":
                    expressions.append(f"{field} < {val}")
                elif op == "$lte":
                    expressions.append(f"{field} <= {val}")
                elif op == "$in":
                    vals = ", ".join(
                        f'"{_escape_string(v)}"' if isinstance(v, str) else str(v)
                        for v in val
                    )
                    expressions.append(f"{field} in [{vals}]")

    return " and ".join(expressions) if expressions else None
