from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ChatConversation, ChatMessage
from bigrag.exceptions import NotFoundError
from bigrag.models.chat import ChatConversationResponse, ChatListResponse, ChatMessageResponse
from bigrag.services.collection_scope import assert_collection_matches_pin

from .formatting import _conversation_response, _message_response
from .types import PreparedChatTurn


async def list_conversations(
    session: AsyncSession,
    user: dict,
    *,
    limit: int = 50,
    offset: int = 0,
) -> ChatListResponse:
    owner_id = UUID(user["id"])
    filters = [ChatConversation.owner_id == owner_id]
    pinned = user.get("collection")
    if pinned:
        filters.append(ChatConversation.collection_name == pinned)
    count_stmt = sa.select(sa.func.count()).select_from(ChatConversation).where(*filters)
    total = int(await session.scalar(count_stmt) or 0)
    stmt = (
        sa.select(
            ChatConversation,
            sa.func.count(ChatMessage.id).label("message_count"),
            sa.func.max(ChatMessage.created_at).label("last_message_at"),
        )
        .outerjoin(ChatMessage, ChatMessage.conversation_id == ChatConversation.id)
        .where(*filters)
        .group_by(ChatConversation.id)
        .order_by(sa.desc(ChatConversation.updated_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).all()
    return ChatListResponse(
        conversations=[
            _conversation_response(
                conversation,
                message_count=int(message_count or 0),
                last_message_at=last_message_at,
            )
            for conversation, message_count, last_message_at in rows
        ],
        total=total,
    )


async def get_conversation_detail(
    session: AsyncSession,
    user: dict,
    conversation_id: UUID,
) -> tuple[ChatConversationResponse, list[ChatMessageResponse]]:
    conversation = await _get_owned_conversation(session, user, conversation_id)
    messages = list(
        (
            await session.scalars(
                sa.select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation.id)
                .order_by(ChatMessage.created_at.asc())
            )
        ).all()
    )
    last_message_at = messages[-1].created_at if messages else None
    return (
        _conversation_response(
            conversation,
            message_count=len(messages),
            last_message_at=last_message_at,
        ),
        [_message_response(message) for message in messages],
    )


async def update_conversation_title(
    session: AsyncSession,
    user: dict,
    conversation_id: UUID,
    title: str,
) -> ChatConversationResponse:
    conversation = await _get_owned_conversation(session, user, conversation_id)
    conversation.title = title.strip()
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    return _conversation_response(conversation)


async def delete_conversation(
    session: AsyncSession,
    user: dict,
    conversation_id: UUID,
) -> None:
    conversation = await _get_owned_conversation(session, user, conversation_id)
    await session.delete(conversation)
    await session.commit()


async def _get_owned_conversation(
    session: AsyncSession,
    user: dict,
    conversation_id: UUID,
) -> ChatConversation:
    owner_id = UUID(user["id"])
    conversation = await session.scalar(
        sa.select(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .where(ChatConversation.owner_id == owner_id)
    )
    if conversation is None:
        raise NotFoundError("Conversation", str(conversation_id))
    pinned = user.get("collection")
    if pinned and conversation.collection_name:
        assert_collection_matches_pin(pinned, conversation.collection_name)
    return conversation


async def _recent_history(
    session: AsyncSession,
    conversation_id: UUID,
    limit: int,
) -> list[ChatMessage]:
    limit = max(0, limit)
    if limit == 0:
        return []
    rows = list(
        (
            await session.scalars(
                sa.select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .where(ChatMessage.status == "complete")
                .where(ChatMessage.role.in_(("user", "assistant")))
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    rows.reverse()
    return rows


async def _store_assistant_message(
    session: AsyncSession,
    prepared: PreparedChatTurn,
    content: str,
) -> ChatMessage:
    assistant = ChatMessage(
        conversation_id=prepared.conversation.id,
        role="assistant",
        content=content,
        model_provider=prepared.model_provider,
        model=prepared.model,
        status="complete",
        retrieval=prepared.retrieval,
    )
    prepared.conversation.updated_at = datetime.now(UTC)
    session.add(assistant)
    await session.flush()
    await session.commit()
    return assistant


async def _store_assistant_error(
    session: AsyncSession,
    prepared: PreparedChatTurn,
    error: str,
) -> ChatMessage:
    assistant = ChatMessage(
        conversation_id=prepared.conversation.id,
        role="assistant",
        content="",
        model_provider=prepared.model_provider,
        model=prepared.model,
        status="error",
        error_message=error,
        retrieval=prepared.retrieval,
    )
    prepared.conversation.updated_at = datetime.now(UTC)
    session.add(assistant)
    await session.flush()
    await session.commit()
    return assistant
