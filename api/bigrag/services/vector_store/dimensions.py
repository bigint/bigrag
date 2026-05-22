from __future__ import annotations

import re
from typing import Any

_VECTOR_DIMENSION_PATTERN = re.compile(r"^\[(\d+)]f(?:16|32)$")
_TURBOPUFFER_MISMATCH_PATTERN = re.compile(r"dimensionality=(\d+)\s+expected=(\d+)")


class VectorStoreDimensionMismatchError(ValueError):
    def __init__(
        self,
        *,
        collection: str,
        namespace: str,
        expected: int,
        actual: int | None,
    ) -> None:
        actual_text = (
            f"{actual} dimensions" if actual is not None else "a different vector dimension"
        )
        super().__init__(
            f"Collection '{collection}' is configured for {expected}-dimensional embeddings, "
            f"but Turbopuffer namespace '{namespace}' already uses {actual_text}. "
            "Truncate or delete the collection before changing embedding dimensions, "
            "or use a different Turbopuffer namespace prefix."
        )
        self.collection = collection
        self.namespace = namespace
        self.expected = expected
        self.actual = actual


def collection_schema(
    dimension: int,
    public_id_field: str = "bigrag_id",
) -> dict[str, dict[str, Any]]:
    return {
        "vector": {"type": f"[{dimension}]f32", "ann": True},
        public_id_field: {"type": "string"},
        "document_id": {"type": "string"},
        "chunk_index": {"type": "int"},
        "text": {"type": "string", "full_text_search": True},
    }


def vector_dimension(schema: dict[str, Any] | None) -> int | None:
    if not schema:
        return None
    vector_config = schema.get("vector")
    if isinstance(vector_config, dict):
        type_name = vector_config.get("type")
    else:
        type_name = getattr(vector_config, "type", None)
    if not isinstance(type_name, str):
        return None
    match = _VECTOR_DIMENSION_PATTERN.match(type_name)
    if match is None:
        return None
    return int(match.group(1))


def write_payload_dimension(payload: dict[str, Any]) -> int | None:
    rows = payload.get("upsert_rows")
    if not isinstance(rows, list) or not rows:
        return None
    vector = rows[0].get("vector") if isinstance(rows[0], dict) else None
    if not isinstance(vector, list):
        return None
    return len(vector)


def turbopuffer_error_message(error: Any) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        detail = body.get("error") or body.get("message")
        if detail:
            return str(detail)
    return str(error)


def turbopuffer_mismatch_dimension(message: str) -> int | None:
    match = _TURBOPUFFER_MISMATCH_PATTERN.search(message)
    if match is None:
        return None
    return int(match.group(2))


def is_turbopuffer_dimension_mismatch(message: str) -> bool:
    return "dimensionality" in message and "expected" in message
