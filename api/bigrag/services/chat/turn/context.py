from __future__ import annotations

import json
from typing import Any

from bigrag.models.chat import ChatSource
from bigrag.services.multimodal_assets import image_content_parts_for_refs


async def _model_messages(
    *,
    system_prompt: str,
    collection: str,
    sources: list[ChatSource],
    user_message: str,
    max_context_chars: int,
    multimodal: bool,
) -> list[dict[str, Any]]:
    context = _context_block(sources, max_context_chars, include_elements=multimodal)
    combined_system = (
        f'{system_prompt}\n\nRetrieved context from collection "{collection}":\n\n{context}'
    )
    user_content: str | list[dict[str, Any]] = user_message
    if multimodal:
        refs = [
            ref.model_dump(mode="json") for source in sources for ref in source.multimodal_elements
        ]
        image_parts = await image_content_parts_for_refs(refs)
        if image_parts:
            user_content = [{"type": "text", "text": user_message}, *image_parts]
    return [
        {"role": "system", "content": combined_system},
        {"role": "user", "content": user_content},
    ]


def _context_block(
    sources: list[ChatSource],
    max_context_chars: int,
    *,
    include_elements: bool,
) -> str:
    if not sources:
        return "(no matching chunks were found)"
    remaining = max(100, min(max_context_chars, 200_000))
    parts: list[str] = []
    for idx, source in enumerate(sources, start=1):
        prefix = f"[{idx}]{_source_label(source)} "
        metadata_text = _source_metadata_context(source)
        element_text = _source_element_context(source) if include_elements else ""
        budget = remaining - len(prefix) - len(metadata_text) - len(element_text) - 16
        if budget <= 0:
            break
        text = source.text[:budget]
        parts.append(f"{prefix}{text}{metadata_text}{element_text}")
        remaining -= len(prefix) + len(text) + len(metadata_text) + len(element_text)
    return "\n\n---\n\n".join(parts)


def _source_label(source: ChatSource) -> str:
    label_parts = []
    if source.document_id:
        label_parts.append(f"document_id {source.document_id}")
    if source.document_filename:
        label_parts.append(f"filename {source.document_filename}")
    if source.chunk_index is not None:
        label_parts.append(f"chunk {source.chunk_index}")
    if source.page_no is not None:
        label_parts.append(f"page {source.page_no}")
    return f" ({', '.join(label_parts)})" if label_parts else ""


def _source_metadata_context(source: ChatSource) -> str:
    if not isinstance(source.metadata, dict):
        return ""
    raw_metadata = source.metadata.get("document_metadata")
    if raw_metadata is None and source.chunk_index is None:
        raw_metadata = source.metadata
    if not isinstance(raw_metadata, dict) or not raw_metadata:
        return ""
    try:
        metadata = json.dumps(raw_metadata, ensure_ascii=True, sort_keys=True)
    except TypeError:
        return ""
    return f"\nDocument metadata: {metadata[:1600]}"


def _source_element_context(source: ChatSource) -> str:
    if not source.multimodal_elements:
        return ""
    lines = []
    for element in source.multimodal_elements[:5]:
        detail = element.summary or element.caption or element.text
        if detail:
            lines.append(f"- {element.kind}: {detail[:600]}")
        else:
            lines.append(f"- {element.kind}")
    return "\n\nRetrieved elements:\n" + "\n".join(lines)
