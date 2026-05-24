from __future__ import annotations

from typing import Any

from bigrag.services.document_elements import element_refs_for_chunk


def build_batch_metadata(
    batch_chunks: list,
    *,
    document_id: str,
    batch_start: int,
    elements: list,
    include_elements: bool,
) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for chunk_offset, c in enumerate(batch_chunks):
        item: dict[str, Any] = {"char_start": c.char_start, "char_end": c.char_end}
        refs = (
            element_refs_for_chunk(
                elements,
                document_id=document_id,
                chunk_start=c.char_start,
                chunk_end=c.char_end,
                chunk_index=batch_start + chunk_offset,
            )
            if include_elements
            else []
        )
        if refs:
            item["multimodal_elements"] = refs
            item["content_kinds"] = sorted({ref["kind"] for ref in refs})
        metadata.append(item)
    return metadata
