from __future__ import annotations

from datetime import UTC, datetime

import orjson

from bigrag.services.event_bus import IngestionEvent

STEP_TO_EVENT = {
    "processing": "document.processing",
    "complete": "document.ready",
    "failed": "document.failed",
}


def matches_webhook(webhook: dict, event: str, collection: str) -> bool:
    if not webhook.get("active", True):
        return False
    if event not in webhook.get("events", []):
        return False
    collections = webhook.get("collections")
    if collections is not None and collection not in collections:
        return False
    return True


def build_payload(webhook_event: str, event: IngestionEvent, collection: str) -> str:
    from bigrag.services.error_sanitize import sanitize_message_text

    data = {
        "event": webhook_event,
        "timestamp": datetime.now(UTC).isoformat(),
        "collection": collection,
        "document_id": event.document_id,
        "status": event.status,
        "chunk_count": event.detail.get("chunks", 0),
        "error_message": sanitize_message_text(str(event.message))
        if event.status == "failed"
        else None,
    }
    return orjson.dumps(data).decode()
