from __future__ import annotations

import random
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ChatQuestionSuggestion, Document
from bigrag.exceptions import ValidationError
from bigrag.models.chat import ChatQuestionSuggestionsRequest, ChatQuestionSuggestionsResponse
from bigrag.services.chat.questions.generation import (
    CHUNK_LIMIT,
    DOCUMENT_LIMIT,
    generate_questions_text,
    parse_questions,
)
from bigrag.services.chat.turn import (
    _resolve_api_credentials,
    _resolve_base_url,
    assert_credentials_allowed_for_base_url,
)
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.runtime_settings import get_values
from bigrag.services.vector_store import vector_store


async def get_question_suggestions(
    session: AsyncSession,
    user: dict,
    collection_name: str,
) -> ChatQuestionSuggestionsResponse:
    collection_name = collection_name.strip()
    collection = await _assert_collection_allowed(user, collection_name)
    row = await session.scalar(
        sa.select(ChatQuestionSuggestion).where(
            ChatQuestionSuggestion.collection_id == collection["id"]
        )
    )
    return _question_suggestions_response(collection_name, row)


async def generate_question_suggestions(
    session: AsyncSession,
    user: dict,
    body: ChatQuestionSuggestionsRequest,
) -> ChatQuestionSuggestionsResponse:
    collection_name = body.collection.strip()
    collection = await _assert_collection_allowed(user, collection_name)
    runtime = await get_values(["chat_provider", "chat_model", "chat_base_url", "chat_temperature"])
    model = body.model or runtime["chat_model"]
    temperature = body.temperature if body.temperature is not None else runtime["chat_temperature"]
    credentials = await _resolve_api_credentials(
        session,
        user,
        SimpleNamespace(provider_api_key=None),
    )
    base_url = await _resolve_base_url(None, runtime["chat_base_url"])
    assert_credentials_allowed_for_base_url(
        credentials,
        base_url,
        request_base_url=None,
        provider=runtime["chat_provider"],
    )
    documents = await _sample_documents(session, collection["id"])
    chunks = await _sample_chunks(collection_name, collection, documents)
    text = await generate_questions_text(
        model=model,
        temperature=temperature,
        credentials=credentials,
        base_url=base_url,
        collection_name=collection_name,
        documents=documents,
        chunks=chunks,
    )
    questions = parse_questions(text)
    generated_at = datetime.now(UTC)
    await _save_question_suggestions(
        session=session,
        collection_id=collection["id"],
        questions=questions,
        model=model,
        generated_by=_user_id(user),
        generated_at=generated_at,
    )
    return ChatQuestionSuggestionsResponse(
        collection=collection_name,
        questions=questions,
        generated_at=generated_at,
        model=model,
    )


async def _assert_collection_allowed(user: dict, collection_name: str) -> dict:
    pinned = user.get("collection")
    if pinned:
        assert_collection_matches_pin(pinned, collection_name)
    return await get_collection_or_404(collection_name)


def _question_suggestions_response(
    collection_name: str,
    row: ChatQuestionSuggestion | None,
) -> ChatQuestionSuggestionsResponse:
    if row is None:
        return ChatQuestionSuggestionsResponse(
            collection=collection_name,
            questions=[],
            generated_at=None,
            model=None,
        )
    return ChatQuestionSuggestionsResponse(
        collection=collection_name,
        questions=_stored_questions(row.questions),
        generated_at=row.generated_at,
        model=row.model,
    )


def _stored_questions(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _user_id(user: dict) -> UUID | None:
    try:
        return UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError):
        return None


async def _save_question_suggestions(
    *,
    session: AsyncSession,
    collection_id: UUID,
    questions: list[str],
    model: str,
    generated_by: UUID | None,
    generated_at: datetime,
) -> None:
    stmt = pg_insert(ChatQuestionSuggestion).values(
        collection_id=collection_id,
        questions=questions,
        model=model,
        generated_by=generated_by,
        generated_at=generated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ChatQuestionSuggestion.collection_id],
        set_={
            "questions": stmt.excluded.questions,
            "model": stmt.excluded.model,
            "generated_by": stmt.excluded.generated_by,
            "generated_at": stmt.excluded.generated_at,
            "updated_at": sa.func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()


async def _sample_documents(session: AsyncSession, collection_id: object) -> list[Document]:
    rows = await session.scalars(
        sa.select(Document)
        .where(Document.collection_id == collection_id)
        .where(Document.status == "ready")
        .where(Document.chunk_count > 0)
        .order_by(sa.func.random())
        .limit(DOCUMENT_LIMIT)
    )
    documents = list(rows.all())
    if not documents:
        raise ValidationError("Generate questions after this collection has ready documents.")
    return documents


async def _sample_chunks(
    collection_name: str,
    collection: dict,
    documents: list[Document],
) -> list[dict]:
    out: list[dict] = []
    for document in documents:
        max_offset = max(0, int(document.chunk_count or 0) - CHUNK_LIMIT)
        offset = random.randint(0, max_offset) if max_offset else 0
        chunks, _total = await vector_store.get_chunks(
            collection_name,
            str(document.id),
            limit=CHUNK_LIMIT,
            offset=offset,
            provider=collection.get("vector_store_provider"),
        )
        for chunk in chunks:
            item = dict(chunk)
            item["document_filename"] = document.filename
            out.append(item)
    return out
