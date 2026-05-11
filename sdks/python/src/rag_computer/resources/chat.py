"""Chat resource."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from rag_computer.types.chat import (
    ChatBody,
    ChatCreateResponse,
    ChatDetailResponse,
    ChatListResponse,
    ChatStreamEvent,
)

if TYPE_CHECKING:
    from rag_computer._core import RagComputerCore


class ChatResource:
    """Resource namespace for production chat operations.

    Access via ``client.chat``.
    """

    def __init__(self, client: RagComputerCore) -> None:
        self._client = client

    async def create(self, body: ChatBody) -> ChatCreateResponse:
        """Create a non-streaming chat turn."""
        payload = dict(body)
        payload["stream"] = False
        return await self._client._request("POST", "/v1/chat", json=payload)

    async def stream(self, body: ChatBody) -> AsyncGenerator[ChatStreamEvent, None]:
        """Stream a chat turn as SSE events.

        Yields dictionaries with ``event`` and ``data`` keys. Token deltas use
        ``{"event": "delta", "data": {"delta": "..."}}``.
        """
        payload = dict(body)
        payload["stream"] = True
        url = f"{self._client.base_url}/v1/chat"
        headers = self._client._headers()
        headers["Content-Type"] = "application/json"

        async with self._client._client.stream(
            "POST",
            url,
            json=payload,
            headers=headers,
            timeout=self._client.timeout,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                await self._client._throw_for_status(response)

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                frames = buffer.split("\n\n")
                buffer = frames.pop() or ""
                for frame in frames:
                    event = _parse_frame(frame)
                    if event is not None:
                        yield event

    async def list(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ChatListResponse:
        """List owned chat conversations."""
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request("GET", "/v1/chat", params=params)

    async def get(self, conversation_id: str) -> ChatDetailResponse:
        """Get a conversation and its messages."""
        return await self._client._request("GET", f"/v1/chat/{conversation_id}")

    async def update(self, conversation_id: str, *, title: str) -> ChatDetailResponse:
        """Rename a conversation."""
        return await self._client._request(
            "PATCH",
            f"/v1/chat/{conversation_id}",
            json={"title": title},
        )

    async def delete(self, conversation_id: str) -> dict[str, str]:
        """Delete a conversation."""
        return await self._client._request("DELETE", f"/v1/chat/{conversation_id}")


def _parse_frame(frame: str) -> ChatStreamEvent | None:
    event_name = "message"
    data_lines: list[str] = []
    for line in frame.splitlines():
        if line.startswith("event: "):
            event_name = line[7:].strip()
        elif line.startswith("data: "):
            data_lines.append(line[6:])
    payload = "\n".join(data_lines)
    if not payload or payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = {"raw": payload}
    if not isinstance(data, dict):
        data = {"value": data}
    return {"event": event_name, "data": data}
