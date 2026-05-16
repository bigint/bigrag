from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ChatRole = Literal["user", "assistant", "system"]
ChatProvider = Literal["openai", "openai_compatible"]
ChatSearchMode = Literal["semantic", "keyword", "hybrid"]


class ChatCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=200_000)
    conversation_id: UUID | None = None
    collection: str | None = Field(default=None, min_length=1, max_length=120)
    stream: bool = True
    model_provider: ChatProvider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_k: int | None = Field(default=None, ge=1, le=100)
    search_mode: ChatSearchMode | None = None
    min_score: float | None = None
    rerank: bool | None = None
    filters: dict | None = None
    system_prompt: str | None = Field(default=None, max_length=20_000)
    provider_api_key: str | None = Field(default=None, max_length=10_000)
    provider_base_url: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def require_collection_for_new_chat(self) -> ChatCreateRequest:
        if self.conversation_id is None and not self.collection:
            raise ValueError("collection is required when starting a new conversation")
        return self


class ChatUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)


class ChatQuestionSuggestionsRequest(BaseModel):
    collection: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class ChatQuestionSuggestionsResponse(BaseModel):
    collection: str
    questions: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None
    model: str | None = None


class ChatSource(BaseModel):
    id: str
    text: str
    score: float
    document_id: str | None = None
    document_filename: str | None = None
    chunk_index: int | None = None
    page_no: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict = Field(default_factory=dict)


class ChatTimings(BaseModel):
    embed_ms: float = 0.0
    search_ms: float = 0.0
    rerank_ms: float = 0.0
    cache_ms: float = 0.0
    total_ms: float = 0.0
    cache_hit: bool = False


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: ChatRole
    content: str
    status: Literal["complete", "error"] = "complete"
    error_message: str | None = None
    model_provider: str | None = None
    model: str | None = None
    retrieval: dict = Field(default_factory=dict)
    sources: list[ChatSource] = Field(default_factory=list)
    created_at: datetime


class ChatConversationResponse(BaseModel):
    id: str
    title: str
    collection: str | None = None
    model_provider: str
    model: str
    temperature: float
    top_k: int
    search_mode: str
    min_score: float | None = None
    rerank: bool | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None


class ChatListResponse(BaseModel):
    conversations: list[ChatConversationResponse]
    total: int


class ChatDetailResponse(BaseModel):
    conversation: ChatConversationResponse
    messages: list[ChatMessageResponse]


class ChatCreateResponse(BaseModel):
    conversation: ChatConversationResponse
    message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    sources: list[ChatSource] = Field(default_factory=list)
    timings: ChatTimings | None = None


class ChatDeleteResponse(BaseModel):
    status: Literal["deleted"] = "deleted"
