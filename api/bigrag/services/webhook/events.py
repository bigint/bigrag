from __future__ import annotations

DOCUMENT_STEP_EVENTS = {
    "processing": "document.processing",
    "complete": "document.ready",
    "failed": "document.failed",
}

DOCUMENT_EVENTS = frozenset(
    {
        *DOCUMENT_STEP_EVENTS.values(),
        "document.deleted",
    }
)

COLLECTION_EVENTS = frozenset(
    {
        "collection.created",
        "collection.updated",
        "collection.deleted",
        "collection.truncated",
    }
)

CONNECTOR_SYNC_EVENTS = frozenset(
    {
        "connector.sync.started",
        "connector.sync.completed",
        "connector.sync.failed",
        "connector.sync.needs_reauth",
    }
)

BACKUP_EVENTS = frozenset(
    {
        "backup.started",
        "backup.succeeded",
        "backup.failed",
    }
)

VALID_EVENTS = DOCUMENT_EVENTS | COLLECTION_EVENTS | CONNECTOR_SYNC_EVENTS | BACKUP_EVENTS
