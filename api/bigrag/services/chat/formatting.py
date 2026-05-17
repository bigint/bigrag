from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

import orjson

from bigrag.exceptions import NotFoundError, ServerError, UpstreamError, ValidationError
from bigrag.models.chat import ChatMessageResponse, ChatRole, ChatSource

_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def _safe_chat_error(exc: Exception) -> str:
    if isinstance(exc, (ValidationError, NotFoundError, ServerError, UpstreamError)):
        message = str(exc)
    else:
        message = getattr(exc, "message", None) or str(exc) or "Chat request failed"
    return _SECRET_RE.sub("sk-[REDACTED]", message)[:500]


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
