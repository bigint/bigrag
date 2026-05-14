from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from bigrag.db.models import ChatConversation, ChatMessage
from bigrag.exceptions import NotFoundError, ServerError, UpstreamError, ValidationError
from bigrag.models.chat import ChatConversationResponse, ChatMessageResponse, ChatSource

_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def _safe_chat_error(exc: Exception) -> str:
    if isinstance(exc, (ValidationError, NotFoundError, ServerError, UpstreamError)):
        message = str(exc)
    else:
        message = getattr(exc, "message", None) or str(exc) or "Chat request failed"
    return _SECRET_RE.sub("sk-[REDACTED]", message)[:500]


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _done_sse() -> str:
    return "data: [DONE]\n\n"


def _as_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _title_from_message(message: str) -> str:
    compact = " ".join(message.strip().split())
    if not compact:
        return "New chat"
    return compact[:77] + "..." if len(compact) > 80 else compact


def _conversation_response(
    conversation: ChatConversation,
    *,
    message_count: int = 0,
    last_message_at: datetime | None = None,
) -> ChatConversationResponse:
    return ChatConversationResponse(
        id=str(conversation.id),
        title=conversation.title,
        collection=conversation.collection_name,
        model_provider=conversation.model_provider,
        model=conversation.model,
        temperature=conversation.temperature,
        top_k=conversation.default_top_k,
        search_mode=conversation.default_search_mode,
        min_score=conversation.default_min_score,
        rerank=conversation.default_rerank,
        message_count=message_count,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_message_at=last_message_at,
    )


def _message_response(message: ChatMessage) -> ChatMessageResponse:
    retrieval = dict(message.retrieval or {})
    raw_sources = retrieval.get("sources")
    sources: list[ChatSource] = []
    if isinstance(raw_sources, list):
        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            try:
                sources.append(ChatSource(**raw))
            except ValueError:
                continue
    return ChatMessageResponse(
        id=str(message.id),
        conversation_id=str(message.conversation_id),
        role=message.role,  # type: ignore[arg-type]
        content=message.content,
        status=message.status,  # type: ignore[arg-type]
        error_message=message.error_message,
        model_provider=message.model_provider,
        model=message.model,
        retrieval=retrieval,
        sources=sources,
        created_at=message.created_at,
    )


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
