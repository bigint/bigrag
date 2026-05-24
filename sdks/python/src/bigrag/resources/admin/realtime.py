from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from bigrag._realtime import RealtimeConnection
from bigrag.types.admin import AdminRealtimeEvent

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminRealtimeResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    def documents(
        self,
        collection: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order: str | None = None,
        q: str | None = None,
        sort: str | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.collections.documents",
            {
                "collection": collection,
                "status": status,
                "limit": limit,
                "offset": offset,
                "order": order,
                "q": q,
                "sort": sort,
            },
        )

    def document_batch_status(
        self, collection: str, document_ids: list[str]
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.collections.documents.batch_status",
            {"collection": collection, "document_ids": document_ids},
        )

    def document(
        self, collection: str, document_id: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.collections.documents.detail",
            {"collection": collection, "document_id": document_id},
        )

    def upload_session(
        self, collection: str, session_id: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.collections.upload_session",
            {"collection": collection, "session_id": session_id},
        )

    def collection_stats(self, collection: str) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("admin.collections.stats", {"collection": collection})

    def connector_sources(
        self, provider: str, *, collection: str | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.connectors.sources",
            {"provider": provider, "collection": collection},
        )

    def connector_sync_jobs(
        self,
        provider: str,
        *,
        collection: str | None = None,
        source_id: str | None = None,
        limit: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.connectors.sync_jobs",
            {
                "provider": provider,
                "collection": collection,
                "source_id": source_id,
                "limit": limit,
            },
        )

    def backups(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("admin.backups", {"limit": limit, "offset": offset})

    def access_overview(
        self, *, window_days: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("admin.access.overview", {"window_days": window_days})

    def access_logs(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        collection: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_family: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.access.logs",
            {
                "action": action,
                "actor_id": actor_id,
                "collection": collection,
                "method": method,
                "path": path,
                "status_family": status_family,
                "success": success,
                "limit": limit,
                "offset": offset,
            },
        )

    def audit(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        resource_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "admin.audit",
            {
                "action": action,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "limit": limit,
                "offset": offset,
            },
        )

    def usage(self, *, window_days: int | None = None) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("admin.usage", {"window_days": window_days})

    def platform_stats(self) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("admin.platform.stats")

    def platform_readiness(self) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("admin.platform.readiness")

    def custom(
        self, topic: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        if not topic.startswith("admin."):
            raise ValueError("admin.realtime.custom topic must start with admin.")
        return self._stream(topic, params or {})

    async def _stream(
        self, topic: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        connection = RealtimeConnection(self._client)
        try:
            async for message in connection.subscribe(topic, params or {}):
                yield message
                if message["type"] == "complete":
                    return
        finally:
            await connection.close()
