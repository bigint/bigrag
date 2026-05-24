from __future__ import annotations

import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, DocumentElement
from bigrag.services.document_elements.types import (
    ELEMENT_TEXT_LIMIT,
    ENRICHABLE_KINDS,
    DocumentElementPayload,
    _valid_kind,
)


@dataclass(frozen=True)
class DocumentElementCounts:
    total: int
    pending_enrichment: int


async def replace_document_elements(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    elements: list[DocumentElementPayload],
    enrichment_enabled: bool,
) -> DocumentElementCounts:
    document = await session.get(Document, document_id)
    if document is None:
        return DocumentElementCounts(total=0, pending_enrichment=0)
    await session.execute(
        sa.delete(DocumentElement).where(DocumentElement.document_id == document_id)
    )
    rows = []
    for index, element in enumerate(elements):
        rows.append(
            DocumentElement(
                document_id=document_id,
                collection_id=document.collection_id,
                element_index=index,
                kind=_valid_kind(element.kind),
                text=element.text[:ELEMENT_TEXT_LIMIT],
                summary=element.summary,
                caption=element.caption,
                asset_path=None,
                page_no=element.page_no,
                bbox=element.bbox,
                char_start=element.char_start,
                char_end=element.char_end,
                surrounding_context=element.surrounding_context,
                meta=element.metadata,
                enrichment_status=_enrichment_status(element, enrichment_enabled),
            )
        )
    session.add_all(rows)
    document.multimodal_element_count = len(rows)
    await session.flush()
    return DocumentElementCounts(
        total=len(rows),
        pending_enrichment=sum(1 for row in rows if row.enrichment_status == "pending"),
    )


def _enrichment_status(element: DocumentElementPayload, enrichment_enabled: bool) -> str:
    if enrichment_enabled and element.kind in ENRICHABLE_KINDS:
        return "pending"
    return "not_requested"
