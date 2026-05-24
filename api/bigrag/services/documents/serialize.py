from __future__ import annotations

from bigrag.db.models import Document
from bigrag.models.document import DocumentProgressResponse, DocumentResponse


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
