"""Chat types."""

from __future__ import annotations

from bigrag.types._compat import Any, NotRequired, TypedDict


class ChatBody(TypedDict):
    message: str
    conversation_id: NotRequired[str | None]
    collection: NotRequired[str | None]
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
    conversation_id: str
    role: str
    content: str
    status: str
    error_message: str | None
    model_provider: str | None
    model: str | None
    retrieval: dict[str, Any]
    sources: list[ChatSource]
    created_at: str


class ChatConversation(TypedDict):
    id: str
    title: str
    collection: str | None
    model_provider: str
    model: str
    temperature: float
    top_k: int
    search_mode: str
    min_score: float | None
    rerank: bool | None
    message_count: int
    created_at: str
    updated_at: str
    last_message_at: str | None


class ChatListResponse(TypedDict):
    conversations: list[ChatConversation]
    total: int


class ChatDetailResponse(TypedDict):
    conversation: ChatConversation
    messages: list[ChatMessage]


class ChatCreateResponse(TypedDict):
    conversation: ChatConversation
    message: ChatMessage
    assistant_message: ChatMessage
    sources: list[ChatSource]
    timings: NotRequired[dict[str, float] | None]


class ChatStreamEvent(TypedDict):
    event: str
    data: dict[str, Any]
