from __future__ import annotations

from typing import Any

from bigrag.db.models import Document
from bigrag.models.document import DocumentProgressResponse
from bigrag.routers._documents import document_progress_response
from bigrag.services.event_bus import IngestionEvent

TERMINAL_DOCUMENT_STATUSES = {"ready", "failed"}
TERMINAL_PROGRESS_STATUSES = {"complete", "failed"}


def fallback_progress(doc: Document, collection_name: str) -> DocumentProgressResponse:
    doc_id = str(doc.id)
    if doc.status == "ready":
        return document_progress_response(
            document_id=doc_id,
            collection_name=collection_name,
            step="complete",
            status="complete",
            message=f"Ready — {doc.chunk_count} chunks",
            progress=1.0,
            detail={"chunks": doc.chunk_count},
        )
    if doc.status == "failed":
        return document_progress_response(
            document_id=doc_id,
            collection_name=collection_name,
            step="failed",
            status="failed",
            message=doc.error_message or "Ingestion failed",
            progress=0.0,
        )
    if doc.status == "processing":
        return document_progress_response(
            document_id=doc_id,
            collection_name=collection_name,
            step="processing",
            status="processing",
            message="Processing document",
            progress=0.05,
        )
    return document_progress_response(
        document_id=doc_id,
        collection_name=collection_name,
        step="queued",
        status="pending",
        message="Queued for ingestion",
        progress=0.0,
    )


async def document_progress(
    bus: Any,
    doc: Document,
    collection_name: str,
) -> DocumentProgressResponse:
    event = await bus.latest(str(doc.id))
    if event is None or (
        doc.status in TERMINAL_DOCUMENT_STATUSES and event.status not in TERMINAL_PROGRESS_STATUSES
    ):
        return fallback_progress(doc, collection_name)
    return document_progress_response(
        document_id=event.document_id,
        collection_name=event.collection_name or collection_name,
        step=event.step,
        status=event.status,
        message=event.message,
        progress=event.progress,
        detail=event.detail,
    )


def publish_queued_progress(bus: Any, doc: Document, collection_name: str, message: str) -> None:
    bus.publish(
        IngestionEvent(
            document_id=str(doc.id),
            collection_name=collection_name,
            step="queued",
            status="pending",
            message=message,
            progress=0.0,
        )
    )
