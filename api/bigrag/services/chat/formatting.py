from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import orjson

from bigrag.models.chat import ChatMessageResponse, ChatRole, ChatSource
from bigrag.services.error_sanitize import sanitize_error_message


def _safe_chat_error(exc: Exception) -> str:
    return sanitize_error_message(exc, fallback="Chat request failed")


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = orjson.dumps(data, default=str).decode()
    return f"event: {event}\ndata: {payload}\n\n"


def _done_sse() -> str:
    return "data: [DONE]\n\n"


def _as_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _chat_message_response(
    *,
    id: str,
    role: ChatRole,
    content: str,
    created_at: datetime,
    status: str = "complete",
    error_message: str | None = None,
    model_provider: str | None = None,
    model: str | None = None,
    retrieval: dict[str, Any] | None = None,
) -> ChatMessageResponse:
    retrieval = dict(retrieval or {})
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
        id=id,
        role=role,
        content=content,
        status=status,  # type: ignore[arg-type]
        error_message=error_message,
        model_provider=model_provider,
        model=model,
        retrieval=retrieval,
        sources=sources,
        created_at=created_at,
    )


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
