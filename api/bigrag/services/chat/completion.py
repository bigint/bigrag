from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.exceptions import UpstreamError
from bigrag.logging import get_logger
from bigrag.models.chat import ChatCreateRequest, ChatCreateResponse

from .formatting import _conversation_response, _done_sse, _message_response, _safe_chat_error, _sse
from .history import _store_assistant_error, _store_assistant_message, get_conversation_detail
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
        await _store_assistant_error(session, prepared, _safe_chat_error(exc))
        if _is_saved_key_auth_error(exc):
            await _clear_saved_chat_key(session, user)
        logger.warning(
            "chat completion failed",
            conversation_id=str(prepared.conversation.id),
            error_type=exc.__class__.__name__,
            error=_safe_chat_error(exc),
        )
        raise UpstreamError(_safe_chat_error(exc)) from exc

    assistant = await _store_assistant_message(session, prepared, content)
    conversation, messages = await get_conversation_detail(session, user, prepared.conversation.id)
    user_message = next(m for m in messages if m.id == str(prepared.user_message.id))
    assistant_message = next(m for m in messages if m.id == str(assistant.id))
    return ChatCreateResponse(
        conversation=conversation,
        message=user_message,
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
        yield _sse(
            "conversation",
            _conversation_response(prepared.conversation, message_count=1).model_dump(mode="json"),
        )
        yield _sse("user_message", _message_response(prepared.user_message).model_dump(mode="json"))
        yield _sse(
            "sources",
            {
                "collection": prepared.conversation.collection_name,
                "sources": [source.model_dump(mode="json") for source in prepared.sources],
                "timings": prepared.timings.model_dump(mode="json"),
            },
        )

        content_parts: list[str] = []
        async for delta in _stream_model(prepared):
            content_parts.append(delta)
            yield _sse("delta", {"delta": delta})

        assistant = await _store_assistant_message(session, prepared, "".join(content_parts))
        conversation, _messages = await get_conversation_detail(
            session,
            user,
            prepared.conversation.id,
        )
        yield _sse("assistant_message", _message_response(assistant).model_dump(mode="json"))
        yield _sse("done", {"conversation": conversation.model_dump(mode="json")})
        yield _done_sse()
    except Exception as exc:
        message = _safe_chat_error(exc)
        if prepared is not None:
            await _store_assistant_error(session, prepared, message)
            if _is_saved_key_auth_error(exc):
                await _clear_saved_chat_key(session, user)
            logger.warning(
                "chat stream failed",
                conversation_id=str(prepared.conversation.id),
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
