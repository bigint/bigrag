from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from .documents import MultimodalElementRef
from .query import QueryTimings, SearchMode


class ChatQuestionSuggestionsBody(TypedDict):
    collection: str
    model: NotRequired[str | None]
    temperature: NotRequired[float | None]


class ChatQuestionSuggestionsResponse(TypedDict):
    collection: str
    questions: list[str]
    generated_at: str | None
    model: str | None


class ChatBody(TypedDict):
    message: str
    collection: str
    stream: NotRequired[bool]
    model_provider: NotRequired[str]
    model: NotRequired[str]
    temperature: NotRequired[float]
    top_k: NotRequired[int]
    search_mode: NotRequired[SearchMode]
    min_score: NotRequired[float | None]
    rerank: NotRequired[bool | None]
    filters: NotRequired[dict[str, Any] | None]
    multimodal: NotRequired[bool]
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
    multimodal_elements: list[MultimodalElementRef]
    metadata: dict[str, Any]


class ChatMessage(TypedDict):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    status: Literal["complete", "error"]
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


class ChatStreamSourcesData(TypedDict):
    collection: str | None
    sources: list[ChatSource]
    timings: NotRequired[QueryTimings]


class ChatStreamDeltaData(TypedDict):
    delta: str


class ChatStreamErrorData(TypedDict):
    error: str


class ChatStreamUserMessageEvent(TypedDict):
    event: Literal["user_message"]
    data: ChatMessage


class ChatStreamSourcesEvent(TypedDict):
    event: Literal["sources"]
    data: ChatStreamSourcesData


class ChatStreamDeltaEvent(TypedDict):
    event: Literal["delta"]
    data: ChatStreamDeltaData


class ChatStreamAssistantMessageEvent(TypedDict):
    event: Literal["assistant_message"]
    data: ChatMessage


class ChatStreamDoneEvent(TypedDict):
    event: Literal["done"]
    data: dict[str, Any]


class ChatStreamErrorEvent(TypedDict):
    event: Literal["error"]
    data: ChatStreamErrorData


ChatStreamEvent = (
    ChatStreamUserMessageEvent
    | ChatStreamSourcesEvent
    | ChatStreamDeltaEvent
    | ChatStreamAssistantMessageEvent
    | ChatStreamDoneEvent
    | ChatStreamErrorEvent
)
