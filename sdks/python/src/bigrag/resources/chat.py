from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from bigrag._sse import parse_sse_frames
from bigrag.types.chat import (
    ChatBody,
    ChatCreateResponse,
    ChatQuestionSuggestionsBody,
    ChatQuestionSuggestionsResponse,
    ChatStreamEvent,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class ChatResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def create(self, body: ChatBody) -> ChatCreateResponse:
        payload = dict(body)
        payload["stream"] = False
        return await self._client._request("POST", "/v1/chat", json=payload)

    async def get_question_suggestions(
        self, collection: str
    ) -> ChatQuestionSuggestionsResponse:
        return await self._client._request(
            "GET",
            "/v1/chat/question-suggestions",
            params={"collection": collection},
        )

    async def generate_question_suggestions(
        self, body: ChatQuestionSuggestionsBody
    ) -> ChatQuestionSuggestionsResponse:
        return await self._client._request(
            "POST", "/v1/chat/question-suggestions", json=body
        )

    async def stream(self, body: ChatBody) -> AsyncGenerator[ChatStreamEvent, None]:
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

            async for frame in parse_sse_frames(response):
                yield _parse_frame(frame.event, frame.data)


def _parse_frame(event_name: str, payload: str) -> ChatStreamEvent:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = {"raw": payload}
    if not isinstance(data, dict):
        data = {"value": data}
    return {"event": event_name, "data": data}
