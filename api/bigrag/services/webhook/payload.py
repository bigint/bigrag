from __future__ import annotations

from datetime import UTC, datetime

import orjson

from bigrag.services.event_bus import IngestionEvent
from bigrag.services.webhook.events import DOCUMENT_STEP_EVENTS


def matches_webhook(webhook: dict, event: str, collection: str | None) -> bool:
    if not webhook.get("active", True):
        return False
    if event not in webhook.get("events", []):
        return False
    collections = webhook.get("collections")
    if collections is not None and (not collection or collection not in collections):
        return False
    return True


def build_ingestion_payload(webhook_event: str, event: IngestionEvent, collection: str) -> str:
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


def build_event_payload(event: str, collection: str | None, data: dict | None = None) -> str:
    return orjson.dumps(
        {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            "collection": collection,
            "data": data or {},
        }
    ).decode()
