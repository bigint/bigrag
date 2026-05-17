from __future__ import annotations

import json
from typing import TYPE_CHECKING, AsyncGenerator
from urllib.parse import quote

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
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/documents",
            {"status": status, "limit": limit, "offset": offset},
        )

    def document_batch_status(
        self, collection: str, document_ids: list[str]
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/documents/batch-status",
            {"document_ids": ",".join(document_ids)},
        )

    def document(
        self, collection: str, document_id: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}"
        )

    def upload_session(
        self, collection: str, session_id: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/upload-sessions/{quote(session_id, safe='')}"
        )

    def collection_stats(
        self, collection: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/stats"
        )

    def connector_sources(
        self, provider: str, *, collection: str | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/{quote(provider, safe='')}/sources",
            {"collection": collection},
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
            f"/v1/admin/realtime/{quote(provider, safe='')}/sync-jobs",
            {"collection": collection, "source_id": source_id, "limit": limit},
        )

    def backups(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "/v1/admin/realtime/backups", {"limit": limit, "offset": offset}
        )

    def access_overview(
        self, *, window_days: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "/v1/admin/realtime/access/overview", {"window_days": window_days}
        )

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
            "/v1/admin/realtime/access/logs",
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
            "/v1/admin/realtime/audit",
            {
                "action": action,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "limit": limit,
                "offset": offset,
            },
        )

    def usage(
        self, *, window_days: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/usage", {"window_days": window_days})

    def platform_stats(self) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/platform/stats")

    def platform_readiness(self) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/platform/readiness")

    def custom(
        self, path: str, params: dict[str, str | int | bool | None] | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        assert path.startswith(
            "/v1/admin/realtime/"
        ), "admin.realtime.custom path must start with /v1/admin/realtime/"
        return self._stream(path, params or {})

    async def _stream(
        self, path: str, params: dict[str, str | int | bool | None] | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        query = _stream_params(params or {})
        async with self._client._client.stream(
            "GET",
            f"{self._client.base_url}{path}",
            params=query,
            headers=self._client._headers(),
            timeout=self._client.timeout,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                await self._client._throw_for_status(response)
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while True:
                    frame = _pop_sse_frame(buffer)
                    if frame is None:
                        break
                    block, buffer = frame
                    event = _parse_realtime_frame(block)
                    if event is not None:
                        yield event
            if buffer.strip():
                event = _parse_realtime_frame(buffer)
                if event is not None:
                    yield event


def _stream_params(params: dict[str, str | int | bool | None]) -> dict[str, str]:
    query: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            query[key] = "true" if value else "false"
        else:
            query[key] = str(value)
    return query


def _pop_sse_frame(buffer: str) -> tuple[str, str] | None:
    lf = buffer.find("\n\n")
    crlf = buffer.find("\r\n\r\n")
    if lf == -1 and crlf == -1:
        return None
    if lf != -1 and (crlf == -1 or lf < crlf):
        return buffer[:lf], buffer[lf + 2 :]
    return buffer[:crlf], buffer[crlf + 4 :]


def _parse_realtime_frame(frame: str) -> AdminRealtimeEvent | None:
    event = "message"
    data: list[str] = []
    for raw_line in frame.splitlines():
        line = raw_line.rstrip("\r")
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].lstrip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if not data:
        return None
    payload = "\n".join(data)
    if payload == "[DONE]":
        return None
    return {"event": event, "data": json.loads(payload)}
