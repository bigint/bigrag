from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, DocumentElement
from bigrag.models.chat import ChatSource
from bigrag.services._retrieval_filters import FilterCondition, build_filter
from bigrag.services.chat.formatting import _as_uuid, _int_or_none
from bigrag.services.document_elements import element_ref

_DOCUMENT_ID_RE = re.compile(
    r"(?<![0-9a-fA-F])"
    r"(?:"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}"
    r")"
    r"(?![0-9a-fA-F])"
)


async def _sources_for_chat(
    session: AsyncSession,
    *,
    collection: dict,
    message: str,
    filters: dict | None,
    results: list[dict],
) -> list[ChatSource]:
    sources = await _sources_from_results(session, results)
    seen_document_ids = {source.document_id for source in sources if source.document_id}
    exact_sources = await _exact_document_sources(
        session,
        collection=collection,
        message=message,
        filters=filters,
        seen_document_ids=seen_document_ids,
    )
    return [*exact_sources, *sources]


async def _sources_from_results(session: AsyncSession, results: list[dict]) -> list[ChatSource]:
    document_ids = {_as_uuid(row.get("document_id")) for row in results if row.get("document_id")}
    document_ids.discard(None)
    documents = await _documents_by_id(session, document_ids)
    hydrated_refs = await _hydrated_element_refs(session, results)
    sources: list[ChatSource] = []
    for row in results:
        cleaned = {key: value for key, value in row.items() if key != "embedding"}
        metadata = cleaned.get("metadata") if isinstance(cleaned.get("metadata"), dict) else {}
        multimodal_elements = hydrated_refs.get(str(cleaned.get("id"))) or metadata.get(
            "multimodal_elements"
        )
        document_id = str(cleaned["document_id"]) if cleaned.get("document_id") else None
        document = documents.get(document_id or "")
        source_metadata = dict(metadata)
        if document is not None and document.meta:
            source_metadata["document_metadata"] = document.meta
        sources.append(
            ChatSource(
                id=str(cleaned.get("id") or len(sources) + 1),
                text=str(cleaned.get("text") or ""),
                score=float(cleaned.get("score") or 0.0),
                document_id=document_id,
                document_filename=document.filename if document is not None else None,
                chunk_index=_int_or_none(cleaned.get("chunk_index")),
                page_no=_int_or_none(cleaned.get("page_no", metadata.get("page_no"))),
                char_start=_int_or_none(cleaned.get("char_start", metadata.get("char_start"))),
                char_end=_int_or_none(cleaned.get("char_end", metadata.get("char_end"))),
                multimodal_elements=multimodal_elements
                if isinstance(multimodal_elements, list)
                else [],
                metadata=source_metadata,
            )
        )
    return sources


async def _exact_document_sources(
    session: AsyncSession,
    *,
    collection: dict,
    message: str,
    filters: dict | None,
    seen_document_ids: set[str],
) -> list[ChatSource]:
    document_ids = [
        document_id
        for document_id in _document_ids_from_message(message)
        if str(document_id) not in seen_document_ids
    ]
    if not document_ids:
        return []
    rows = await session.scalars(
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .where(Document.id.in_(document_ids))
    )
    return [
        _document_source(document)
        for document in rows.all()
        if _document_matches_filters(document, filters)
    ]


def _document_ids_from_message(message: str) -> list[UUID]:
    out: list[UUID] = []
    for match in _DOCUMENT_ID_RE.finditer(message):
        try:
            document_id = UUID(match.group(0))
        except ValueError:
            continue
        if document_id not in out:
            out.append(document_id)
    return out


def _document_source(document: Document) -> ChatSource:
    metadata = dict(document.meta or {})
    text_parts = [
        f"Document ID: {document.id}",
        f"Document filename/title: {document.filename}",
        f"File type: {document.file_type or 'unknown'}",
        f"Status: {document.status}",
    ]
    if metadata:
        text_parts.append(
            f"Metadata: {json.dumps(metadata, ensure_ascii=True, sort_keys=True)[:2000]}"
        )
    return ChatSource(
        id=f"{document.id}:metadata",
        text="\n".join(text_parts),
        score=1.0,
        document_id=str(document.id),
        document_filename=document.filename,
        metadata=metadata,
    )


def _document_matches_filters(document: Document, filters: dict | None) -> bool:
    if not filters:
        return True
    try:
        expression = build_filter(filters)
    except ValueError:
        return False
    if expression is None:
        return True
    metadata = document.meta or {}
    return all(
        _condition_matches(metadata.get(condition.field), condition)
        for condition in expression.conditions
    )


def _condition_matches(value: object, condition: FilterCondition) -> bool:
    if condition.operator == "eq":
        return value == condition.value
    if condition.operator == "ne":
        return value != condition.value
    if condition.operator == "in":
        return value in condition.value
    if condition.operator == "gt":
        return _ordered_match(value, condition.value, lambda left, right: left > right)
    if condition.operator == "gte":
        return _ordered_match(value, condition.value, lambda left, right: left >= right)
    if condition.operator == "lt":
        return _ordered_match(value, condition.value, lambda left, right: left < right)
    if condition.operator == "lte":
        return _ordered_match(value, condition.value, lambda left, right: left <= right)
    return False


def _ordered_match(value: object, target: object, compare) -> bool:
    try:
        return bool(compare(value, target))
    except TypeError:
        return False


async def _documents_by_id(
    session: AsyncSession,
    document_ids: set[UUID | None],
) -> dict[str, Document]:
    valid_ids = {document_id for document_id in document_ids if document_id is not None}
    if not valid_ids:
        return {}
    rows = await session.scalars(sa.select(Document).where(Document.id.in_(valid_ids)))
    return {str(document.id): document for document in rows.all()}


async def _hydrated_element_refs(
    session: AsyncSession,
    results: list[dict],
) -> dict[str, list[dict[str, Any]]]:
    pairs = []
    by_result: dict[str, list[tuple[str, int]]] = {}
    for row in results:
        result_id = str(row.get("id") or "")
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        refs = metadata.get("multimodal_elements")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            raw_document_id = ref.get("document_id") or row.get("document_id")
            raw_index = ref.get("element_index")
            if raw_document_id is None or raw_index is None:
                continue
            doc_uuid = _as_uuid(raw_document_id)
            try:
                element_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if doc_uuid is None:
                continue
            key = (str(doc_uuid), element_index)
            pairs.append(key)
            by_result.setdefault(result_id, []).append(key)
    if not pairs:
        return {}
    rows = (
        await session.scalars(
            sa.select(DocumentElement).where(
                sa.tuple_(DocumentElement.document_id, DocumentElement.element_index).in_(
                    {(_as_uuid(doc_id), index) for doc_id, index in pairs}
                )
            )
        )
    ).all()
    hydrated = {
        (str(row.document_id), row.element_index): element_ref(
            row, document_id=str(row.document_id)
        )
        for row in rows
    }
    return {
        result_id: [hydrated[key] for key in keys if key in hydrated]
        for result_id, keys in by_result.items()
    }
