from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bigrag.models.chat import ChatMessageResponse, ChatSource, ChatTimings


@dataclass
class ProviderCredential:
    api_key: str
    source: str


@dataclass
class PreparedChatTurn:
    collection: str
    user_message: ChatMessageResponse
    model_messages: list[dict[str, Any]]
    sources: list[ChatSource]
    timings: ChatTimings
    retrieval: dict[str, Any]
    model_provider: str
    model: str
    temperature: float
    credentials: list[ProviderCredential]
    base_url: str | None
