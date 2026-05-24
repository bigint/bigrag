from __future__ import annotations

from typing import Any

from bigrag.db.models import DocumentElement
from bigrag.services.document_elements.types import (
    ELEMENT_REF_TEXT_LIMIT,
    DocumentElementPayload,
    _valid_kind,
)


def element_refs_for_chunk(
    elements: list[DocumentElementPayload],
    *,
    document_id: str,
    chunk_start: int,
    chunk_end: int,
    chunk_index: int,
) -> list[dict[str, Any]]:
    refs = []
    for element in elements:
        if element.kind == "text":
            continue
        if not _element_overlaps_chunk(element, chunk_start, chunk_end, chunk_index):
            continue
        refs.append(element_ref(element, document_id=document_id))
        if len(refs) >= 8:
            break
    return refs


def element_ref(
    element: DocumentElementPayload | DocumentElement, *, document_id: str | None
) -> dict[str, Any]:
    text = getattr(element, "summary", None) or getattr(element, "text", "")
    metadata = getattr(element, "meta", None)
    if metadata is None:
        metadata = getattr(element, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "document_id": document_id,
        "element_index": int(element.element_index),
        "kind": _valid_kind(str(getattr(element, "kind", "unknown"))),
        "text": str(text or "")[:ELEMENT_REF_TEXT_LIMIT],
        "summary": getattr(element, "summary", None),
        "caption": getattr(element, "caption", None),
        "asset_path": getattr(element, "asset_path", None),
        "page_no": getattr(element, "page_no", None),
        "bbox": getattr(element, "bbox", None),
        "metadata": dict(metadata),
    }


def _element_overlaps_chunk(
    element: DocumentElementPayload,
    chunk_start: int,
    chunk_end: int,
    chunk_index: int,
) -> bool:
    if element.char_start is None or element.char_end is None:
        return chunk_index == 0
    return element.char_start < chunk_end and element.char_end > chunk_start
