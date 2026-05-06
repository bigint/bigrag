from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.models.chat import (
    ChatCreateRequest,
    ChatCreateResponse,
    ChatDeleteResponse,
    ChatDetailResponse,
    ChatListResponse,
    ChatUpdateRequest,
)
from bigrag.services import access_log
from bigrag.services.chat import (
    create_chat_completion,
    delete_conversation,
    get_conversation_detail,
    list_conversations,
    stream_chat_completion,
    update_conversation_title,
)

router = APIRouter(prefix="/v1/chat", tags=["chat"])


@router.get("", response_model=ChatListResponse)
async def list_chat_conversations(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatListResponse:
    access_log.set_context(
        request,
        action="chat.list",
        resource_type="chat",
        metadata={"limit": limit, "offset": offset},
    )
    return await list_conversations(session, user, limit=limit, offset=offset)


@router.get("/{conversation_id}", response_model=ChatDetailResponse)
async def get_chat_conversation(
    conversation_id: UUID,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatDetailResponse:
    access_log.set_context(
        request,
        action="chat.read",
        resource_type="chat",
        resource_id=str(conversation_id),
    )
    conversation, messages = await get_conversation_detail(session, user, conversation_id)
    return ChatDetailResponse(conversation=conversation, messages=messages)


@router.post("", response_model=ChatCreateResponse)
async def create_chat(
    body: ChatCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    access_log.set_context(
        request,
        action="chat.generate",
        resource_type="chat",
        collection_name=body.collection,
        metadata={
            **access_log.query_fingerprint(body.message),
            **access_log.filter_summary(body.filters),
            "stream": body.stream,
            "conversation_id": str(body.conversation_id) if body.conversation_id else None,
            "requested_top_k": body.top_k,
            "search_mode": body.search_mode,
            "model": body.model,
        },
    )
    if body.stream:
        return StreamingResponse(
            stream_chat_completion(session, user, body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await create_chat_completion(session, user, body)


@router.patch("/{conversation_id}", response_model=ChatDetailResponse)
async def update_chat_conversation(
    conversation_id: UUID,
    body: ChatUpdateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatDetailResponse:
    access_log.set_context(
        request,
        action="chat.update",
        resource_type="chat",
        resource_id=str(conversation_id),
    )
    if body.title is not None:
        await update_conversation_title(session, user, conversation_id, body.title)
    conversation, messages = await get_conversation_detail(session, user, conversation_id)
    return ChatDetailResponse(conversation=conversation, messages=messages)


@router.delete("/{conversation_id}", response_model=ChatDeleteResponse)
async def delete_chat_conversation(
    conversation_id: UUID,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatDeleteResponse:
    access_log.set_context(
        request,
        action="chat.delete",
        resource_type="chat",
        resource_id=str(conversation_id),
    )
    await delete_conversation(session, user, conversation_id)
    return ChatDeleteResponse()
