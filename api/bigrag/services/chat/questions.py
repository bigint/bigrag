from __future__ import annotations

import json
import random
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ChatQuestionSuggestion, Document
from bigrag.exceptions import UpstreamError, ValidationError
from bigrag.models.chat import ChatQuestionSuggestionsRequest, ChatQuestionSuggestionsResponse
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.runtime_settings import get_values
from bigrag.services.vector_store import vector_store

from .provider import _openai_client, _provider_error, _should_try_next_credential
from .turn import _resolve_api_credentials, _resolve_base_url
from .types import ProviderCredential

_QUESTION_COUNT = 5
_DOCUMENT_LIMIT = 6
_CHUNK_LIMIT = 4
_CHUNK_CHARS = 900


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
    runtime = await get_values(["chat_model", "chat_base_url", "chat_temperature"])
    model = body.model or runtime["chat_model"]
    temperature = body.temperature if body.temperature is not None else runtime["chat_temperature"]
    credentials = await _resolve_api_credentials(
        session,
        user,
        SimpleNamespace(provider_api_key=None),
    )
    base_url = await _resolve_base_url(None, runtime["chat_base_url"])
    documents = await _sample_documents(session, collection["id"])
    chunks = await _sample_chunks(collection_name, collection, documents)
    text = await _generate_questions_text(
        model=model,
        temperature=temperature,
        credentials=credentials,
        base_url=base_url,
        collection_name=collection_name,
        documents=documents,
        chunks=chunks,
    )
    questions = _parse_questions(text)
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
        .limit(_DOCUMENT_LIMIT)
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
        max_offset = max(0, int(document.chunk_count or 0) - _CHUNK_LIMIT)
        offset = random.randint(0, max_offset) if max_offset else 0
        chunks, _total = await vector_store.get_chunks(
            collection_name,
            str(document.id),
            limit=_CHUNK_LIMIT,
            offset=offset,
            provider=collection.get("vector_store_provider"),
        )
        for chunk in chunks:
            item = dict(chunk)
            item["document_filename"] = document.filename
            out.append(item)
    return out


async def _generate_questions_text(
    *,
    model: str,
    temperature: float,
    credentials: list[ProviderCredential],
    base_url: str | None,
    collection_name: str,
    documents: list[Document],
    chunks: list[dict],
) -> str:
    try:
        import openai
    except ImportError as exc:
        raise UpstreamError(
            "openai package is required to generate questions",
            public_message="openai package is required to generate questions",
        ) from exc

    prompt = _question_prompt(collection_name, documents, chunks)
    prepared = SimpleNamespace(
        model=model,
        temperature=temperature,
        credentials=credentials,
        base_url=base_url,
    )
    last_error: Exception | None = None
    for credential in credentials:
        client = _openai_client(openai, prepared, credential)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate concise, specific test questions for retrieval "
                            "evaluation. Return JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=max(temperature, 0.7),
                response_format={"type": "json_object"},
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise UpstreamError(
                    "Question generation returned no choices",
                    public_message="Question generation returned no choices",
                )
            return getattr(choices[0].message, "content", None) or ""
        except Exception as exc:
            last_error = exc
            if not _should_try_next_credential(exc, prepared, credential):
                raise _provider_error(exc, credential) from exc
        finally:
            await client.close()
    if last_error is not None:
        raise _provider_error(last_error, credentials[-1]) from last_error
    return ""


def _question_prompt(collection_name: str, documents: list[Document], chunks: list[dict]) -> str:
    filenames = "\n".join(f"- {document.filename}" for document in documents)
    chunk_lines = "\n\n".join(
        (
            f"[{index + 1}] "
            f"{chunk.get('document_filename') or chunk.get('document_id')}\n"
            f"{str(chunk.get('text') or '')[:_CHUNK_CHARS]}"
        )
        for index, chunk in enumerate(chunks[:12])
    )
    shape = '{"questions":["question 1","question 2","question 3","question 4","question 5"]}'
    return (
        f'Collection: "{collection_name}"\n\n'
        f"Ready documents:\n{filenames}\n\n"
        f"Sampled chunks:\n{chunk_lines or '(no chunks available)'}\n\n"
        f"Return exactly this JSON shape: {shape}. "
        "Each question must be answerable from the collection, varied, and useful for "
        "testing retrieval."
    )


def _parse_questions(text: str) -> list[str]:
    try:
        raw = json.loads(_json_object_text(text))
        questions = raw.get("questions") if isinstance(raw, dict) else None
    except (json.JSONDecodeError, ValueError):
        questions = _line_questions(text)
    cleaned = _clean_questions(questions or [])
    if len(cleaned) != _QUESTION_COUNT:
        raise UpstreamError(
            "Question generation did not return five questions",
            public_message="Question generation did not return five questions",
        )
    return cleaned


def _json_object_text(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("missing JSON object")
    return text[start : end + 1]


def _line_questions(text: str) -> list[str]:
    return [
        re.sub(r"^\s*[-*\d.)]+\s*", "", line).strip() for line in text.splitlines() if line.strip()
    ]


def _clean_questions(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = re.sub(r"\s+", " ", value).strip().strip('"')
        if not cleaned or cleaned in out:
            continue
        out.append(cleaned)
        if len(out) == _QUESTION_COUNT:
            break
    return out
