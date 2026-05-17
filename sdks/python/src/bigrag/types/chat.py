from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from .query import QueryTimings


class ChatBody(TypedDict):
    message: str
    collection: str
    stream: NotRequired[bool]
    model_provider: NotRequired[str]
    model: NotRequired[str]
    temperature: NotRequired[float]
    top_k: NotRequired[int]
    search_mode: NotRequired[str]
    min_score: NotRequired[float | None]
    rerank: NotRequired[bool | None]
    filters: NotRequired[dict[str, Any] | None]
    system_prompt: NotRequired[str]
    provider_api_key: NotRequired[str]
    provider_base_url: NotRequired[str | None]


class ChatSource(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    document_filename: str | None
    chunk_index: int | None
    page_no: int | None
    char_start: int | None
    char_end: int | None
    metadata: dict[str, Any]


class ChatMessage(TypedDict):
    id: str
    role: str
    content: str
    status: str
    error_message: str | None
    model_provider: str | None
    model: str | None
    retrieval: dict[str, Any]
    sources: list[ChatSource]
    created_at: str


class ChatCreateResponse(TypedDict):
    message: ChatMessage
    assistant_message: ChatMessage
    sources: list[ChatSource]
    timings: NotRequired[QueryTimings | None]


class ChatStreamEvent(TypedDict):
    event: str
    data: dict[str, Any]
