from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.exceptions import UpstreamError
from bigrag.logging import get_logger
from bigrag.models.chat import ChatCreateRequest, ChatCreateResponse

from .formatting import _chat_message_response, _done_sse, _safe_chat_error, _sse
from .provider import _complete_model, _is_saved_key_auth_error, _stream_model
from .turn import _clear_saved_chat_key, _prepare_chat_turn
from .types import PreparedChatTurn

logger = get_logger("bigrag.chat")


async def create_chat_completion(
    session: AsyncSession,
    user: dict,
    body: ChatCreateRequest,
) -> ChatCreateResponse:
    prepared = await _prepare_chat_turn(session, user, body)
    try:
        content = await _complete_model(prepared)
    except Exception as exc:
        if _is_saved_key_auth_error(exc):
            await _clear_saved_chat_key(session, user)
        logger.warning(
            "chat completion failed",
            collection=prepared.collection,
            error_type=exc.__class__.__name__,
            error=_safe_chat_error(exc),
        )
        raise UpstreamError(_safe_chat_error(exc)) from exc

    assistant_message = _chat_message_response(
        id=str(uuid4()),
        role="assistant",
        content=content,
        model_provider=prepared.model_provider,
        model=prepared.model,
        retrieval=prepared.retrieval,
        created_at=datetime.now(UTC),
    )
    return ChatCreateResponse(
        message=prepared.user_message,
        assistant_message=assistant_message,
        sources=prepared.sources,
        timings=prepared.timings,
    )


async def stream_chat_completion(
    session: AsyncSession,
    user: dict,
    body: ChatCreateRequest,
) -> AsyncIterator[str]:
    prepared: PreparedChatTurn | None = None
    try:
        prepared = await _prepare_chat_turn(session, user, body)
        yield _sse("user_message", prepared.user_message.model_dump(mode="json"))
        yield _sse(
            "sources",
            {
                "collection": prepared.collection,
                "sources": [source.model_dump(mode="json") for source in prepared.sources],
                "timings": prepared.timings.model_dump(mode="json"),
            },
        )

        content_parts: list[str] = []
        async for delta in _stream_model(prepared):
            content_parts.append(delta)
            yield _sse("delta", {"delta": delta})

        assistant = _chat_message_response(
            id=str(uuid4()),
            role="assistant",
            content="".join(content_parts),
            model_provider=prepared.model_provider,
            model=prepared.model,
            retrieval=prepared.retrieval,
            created_at=datetime.now(UTC),
        )
        yield _sse("assistant_message", assistant.model_dump(mode="json"))
        yield _sse("done", {})
        yield _done_sse()
    except Exception as exc:
        message = _safe_chat_error(exc)
        if prepared is not None:
            if _is_saved_key_auth_error(exc):
                await _clear_saved_chat_key(session, user)
            logger.warning(
                "chat stream failed",
                collection=prepared.collection,
                error_type=exc.__class__.__name__,
                error=message,
            )
        else:
            logger.warning(
                "chat stream setup failed",
                error_type=exc.__class__.__name__,
                error=message,
            )
        yield _sse("error", {"error": message})
        yield _done_sse()
