from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.models.chat import (
    ChatCreateRequest,
    ChatCreateResponse,
    ChatQuestionSuggestionsRequest,
    ChatQuestionSuggestionsResponse,
)
from bigrag.services import access_log
from bigrag.services.chat import (
    create_chat_completion,
    generate_question_suggestions,
    get_question_suggestions,
    stream_chat_completion,
)

router = APIRouter(prefix="/v1/chat", tags=["chat"])


@router.get("/question-suggestions", response_model=ChatQuestionSuggestionsResponse)
async def get_chat_question_suggestions(
    request: Request,
    collection: str = Query(min_length=1, max_length=120),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatQuestionSuggestionsResponse:
    access_log.set_context(
        request,
        action="chat.question_suggestions.read",
        resource_type="collection",
        collection_name=collection,
    )
    return await get_question_suggestions(session, user, collection)


@router.post("/question-suggestions", response_model=ChatQuestionSuggestionsResponse)
async def create_chat_question_suggestions(
    body: ChatQuestionSuggestionsRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatQuestionSuggestionsResponse:
    access_log.set_context(
        request,
        action="chat.question_suggestions.generate",
        resource_type="collection",
        collection_name=body.collection,
        metadata={"model": body.model},
    )
    return await generate_question_suggestions(session, user, body)


@router.post("", response_model=ChatCreateResponse)
async def create_chat(
    body: ChatCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
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
            "requested_top_k": body.top_k,
            "search_mode": body.search_mode,
            "model": body.model,
        },
    )
    if body.stream:
        return StreamingResponse(
            stream_chat_completion(user, body, request),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await create_chat_completion(user, body)
