from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bigrag.db.models import ChatConversation, ChatMessage
from bigrag.models.chat import ChatSource, ChatTimings


@dataclass
class ProviderCredential:
    api_key: str
    source: str


@dataclass
class PreparedChatTurn:
    conversation: ChatConversation
    user_message: ChatMessage
    model_messages: list[dict[str, str]]
    sources: list[ChatSource]
    timings: ChatTimings
    retrieval: dict[str, Any]
    model_provider: str
    model: str
    temperature: float
    credentials: list[ProviderCredential]
    base_url: str | None
