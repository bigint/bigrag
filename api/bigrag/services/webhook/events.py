from __future__ import annotations

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
    }
)

VALID_EVENTS = COLLECTION_EVENTS | CONNECTOR_SYNC_EVENTS
