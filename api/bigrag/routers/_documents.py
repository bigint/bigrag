from __future__ import annotations

import json

from bigrag.db.models import Document
from bigrag.logging import get_logger
from bigrag.models.document import DocumentProgressResponse, DocumentResponse
from bigrag.services.tenant_enforcement import enforce_document_tenant_access

logger = get_logger("bigrag.routers.documents")


def check_document_tenant(user: dict, doc: Document, collection: dict) -> None:
    enforce_document_tenant_access(user, collection, doc.meta)


def document_progress_response(
    *,
    document_id: str,
    collection_name: str,
    step: str,
    status: str,
    message: str,
    progress: float,
    detail: dict | None = None,
) -> DocumentProgressResponse:
    return DocumentProgressResponse(
        document_id=document_id,
        collection_name=collection_name,
        step=step,
        status=status,
        message=message,
        progress=max(0.0, min(1.0, progress)),
        detail=detail or {},
    )


def document_response(
    doc: Document,
    *,
    deduped: bool = False,
    progress: DocumentProgressResponse | None = None,
) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        collection_id=str(doc.collection_id),
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        multimodal_element_count=doc.multimodal_element_count,
        status=doc.status,
        error_message=doc.error_message,
        metadata=doc.meta or {},
        content_hash=doc.content_hash,
        deduped=deduped,
        progress=progress,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def parse_form_metadata(raw_metadata: str) -> dict:
    try:
        parsed = json.loads(raw_metadata) if raw_metadata else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
