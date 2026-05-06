from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
from bigrag.db.models import ChatConversation, ChatMessage, Document, UserPreference
from bigrag.exceptions import ValidationError
from bigrag.logging import get_logger
from bigrag.models.chat import (
    ChatConversationResponse,
    ChatCreateRequest,
    ChatCreateResponse,
    ChatListResponse,
    ChatMessageResponse,
    ChatSource,
    ChatTimings,
)
from bigrag.routers.preferences import decrypt_preferences
from bigrag.services import crypto
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_embedding_model_for, get_reranking_config
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.retrieval import retrieve
from bigrag.services.url_security import UnsafeOutboundUrlError, validate_chat_base_url

logger = get_logger("bigrag.chat")

_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
_PROVIDERS = {"openai", "openai_compatible"}

DEFAULT_SYSTEM_PROMPT = (
    "You are bigRAG's grounded chat assistant. Answer using only the retrieved context. "
    "If the context does not contain the answer, say you do not know. Cite every factual "
    "claim with bracketed source numbers like [1] or [2]. Keep answers concise unless the "
    "user asks for detail."
)


@dataclass
class ProviderCredential:
    api_key: str
    source: str


@dataclass
class PreparedChatTurn:
    conversation: ChatConversation
    user_message: ChatMessage
    model_messages: list[dict[str, str]]
    sources: list[ChatSource]
    timings: ChatTimings
    retrieval: dict[str, Any]
    model_provider: str
    model: str
    temperature: float
    credentials: list[ProviderCredential]
    base_url: str | None


def _safe_chat_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        message = detail if isinstance(detail, str) else "Chat request failed"
    elif isinstance(exc, ValidationError):
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
        logger.warning(
            "chat completion failed",
            conversation_id=str(prepared.conversation.id),
            error=f"{exc.__class__.__name__}: {_safe_chat_error(exc)}",
        )
        raise HTTPException(status_code=502, detail=_safe_chat_error(exc)) from exc

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
            logger.warning(
                "chat stream failed",
                conversation_id=str(prepared.conversation.id),
                error=f"{exc.__class__.__name__}: {message}",
            )
        else:
            logger.warning("chat stream setup failed", error=f"{exc.__class__.__name__}: {message}")
        yield _sse("error", {"error": message})
        yield _done_sse()


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
        raise HTTPException(status_code=404, detail="Conversation not found")
    pinned = user.get("collection")
    if pinned and conversation.collection_name:
        assert_collection_matches_pin(pinned, conversation.collection_name)
    return conversation


async def _prepare_chat_turn(
    session: AsyncSession,
    user: dict,
    body: ChatCreateRequest,
) -> PreparedChatTurn:
    owner_id = UUID(user["id"])
    pinned = user.get("collection")

    if body.conversation_id is not None:
        conversation = await _get_owned_conversation(session, user, body.conversation_id)
        if (
            body.collection
            and conversation.collection_name
            and body.collection != conversation.collection_name
        ):
            raise HTTPException(
                status_code=400,
                detail="A conversation cannot switch collections. Start a new chat instead.",
            )
        if not conversation.collection_name:
            raise HTTPException(status_code=400, detail="Conversation is missing its collection")
        collection_name = conversation.collection_name
    else:
        collection_name = body.collection or pinned
        if not collection_name:
            raise HTTPException(status_code=400, detail="collection is required")
        if pinned:
            assert_collection_matches_pin(pinned, collection_name)
        collection = await get_collection_or_404(collection_name)
        conversation = ChatConversation(
            owner_id=owner_id,
            title=_title_from_message(body.message),
            collection_id=collection.get("id"),
            collection_name=collection_name,
            model_provider=_resolve_provider(body.model_provider),
            model=body.model or settings.chat_model,
            system_prompt=body.system_prompt or DEFAULT_SYSTEM_PROMPT,
            default_top_k=body.top_k or min(int(collection.get("default_top_k") or 5), 100),
            default_search_mode=body.search_mode
            or collection.get("default_search_mode", "semantic"),
            default_min_score=body.min_score
            if body.min_score is not None
            else collection.get("default_min_score"),
            default_rerank=body.rerank,
            temperature=body.temperature
            if body.temperature is not None
            else settings.chat_temperature,
        )
        session.add(conversation)
        await session.flush()

    collection = await get_collection_or_404(collection_name)
    _apply_turn_overrides(conversation, body, collection)
    provider = _resolve_provider(conversation.model_provider)
    credentials = await _resolve_api_credentials(session, user, body)
    base_url = await _resolve_base_url(body.provider_base_url)

    prior_messages = await _recent_history(session, conversation.id)

    try:
        embedding_model = get_embedding_model_for(collection)
    except (ImportError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    top_k = max(1, min(int(conversation.default_top_k or 5), 100))
    search_mode = conversation.default_search_mode or collection.get(
        "default_search_mode",
        "semantic",
    )
    min_score = conversation.default_min_score
    outcome = await retrieve(
        collection_name=collection_name,
        query=body.message,
        embedding_model=embedding_model,
        top_k=top_k,
        filters=body.filters,
        min_score=min_score,
        search_mode=search_mode,
        reranking_config=get_reranking_config(collection),
        rerank_override=conversation.default_rerank,
    )
    sources = await _sources_from_results(session, outcome.results)
    timings = ChatTimings(
        embed_ms=outcome.embed_ms,
        search_ms=outcome.search_ms,
        rerank_ms=outcome.rerank_ms,
        total_ms=outcome.total_ms,
    )
    retrieval = {
        "collection": collection_name,
        "query": body.message,
        "top_k": top_k,
        "search_mode": search_mode,
        "min_score": min_score,
        "rerank": conversation.default_rerank,
        "filters": body.filters or {},
        "sources": [source.model_dump(mode="json") for source in sources],
        "timings": timings.model_dump(mode="json"),
    }

    user_message = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=body.message,
        status="complete",
        retrieval={},
    )
    conversation.updated_at = datetime.now(UTC)
    session.add(user_message)
    await session.flush()
    await session.commit()

    model_messages = _model_messages(
        system_prompt=conversation.system_prompt or DEFAULT_SYSTEM_PROMPT,
        collection=collection_name,
        sources=sources,
        prior_messages=prior_messages,
        user_message=body.message,
    )
    return PreparedChatTurn(
        conversation=conversation,
        user_message=user_message,
        model_messages=model_messages,
        sources=sources,
        timings=timings,
        retrieval=retrieval,
        model_provider=provider,
        model=conversation.model,
        temperature=conversation.temperature,
        credentials=credentials,
        base_url=base_url,
    )


def _resolve_provider(provider: str | None) -> str:
    value = (provider or settings.chat_provider or "openai").strip().lower()
    if value not in _PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail="Only openai and openai_compatible chat providers are supported",
        )
    return value


def _apply_turn_overrides(
    conversation: ChatConversation,
    body: ChatCreateRequest,
    collection: dict,
) -> None:
    if body.model_provider is not None:
        conversation.model_provider = _resolve_provider(body.model_provider)
    if body.model is not None:
        conversation.model = body.model
    if body.system_prompt is not None:
        conversation.system_prompt = body.system_prompt or DEFAULT_SYSTEM_PROMPT
    if body.temperature is not None:
        conversation.temperature = body.temperature
    if body.top_k is not None:
        conversation.default_top_k = body.top_k
    elif not conversation.default_top_k:
        conversation.default_top_k = min(int(collection.get("default_top_k") or 5), 100)
    if body.search_mode is not None:
        conversation.default_search_mode = body.search_mode
    elif not conversation.default_search_mode:
        conversation.default_search_mode = collection.get("default_search_mode", "semantic")
    if body.min_score is not None:
        conversation.default_min_score = body.min_score
    if body.rerank is not None:
        conversation.default_rerank = body.rerank


async def _resolve_api_credentials(
    session: AsyncSession,
    user: dict,
    body: ChatCreateRequest,
) -> list[ProviderCredential]:
    if body.provider_api_key and body.provider_api_key.strip():
        return [ProviderCredential(api_key=body.provider_api_key.strip(), source="request")]

    credentials: list[ProviderCredential] = []
    data = await session.scalar(
        sa.select(UserPreference.data).where(UserPreference.user_id == UUID(user["id"]))
    )
    prefs = decrypt_preferences(dict(data)) if isinstance(data, dict) else {}
    chat = prefs.get("chat") if isinstance(prefs.get("chat"), dict) else {}
    playground = prefs.get("playground") if isinstance(prefs.get("playground"), dict) else {}
    _append_credential(credentials, chat.get("openai_key"), "saved chat key")
    _append_credential(credentials, playground.get("openai_key"), "saved playground key")

    if not credentials:
        raise HTTPException(
            status_code=400,
            detail=(
                "Save an OpenAI API key in Chat settings, or pass provider_api_key "
                "with the chat request."
            ),
        )
    return credentials


def _append_credential(
    credentials: list[ProviderCredential],
    raw_api_key: object,
    source: str,
) -> None:
    if not isinstance(raw_api_key, str) or not raw_api_key.strip():
        return
    api_key = raw_api_key.strip()
    if api_key.startswith(crypto._FERNET_PREFIX):
        raise HTTPException(
            status_code=500,
            detail=f"{source} cannot be decrypted. Configure BIGRAG_MASTER_KEY.",
        )
    if any(existing.api_key == api_key for existing in credentials):
        return
    credentials.append(ProviderCredential(api_key=api_key, source=source))


async def _resolve_base_url(raw_base_url: str | None) -> str | None:
    candidate = raw_base_url if raw_base_url is not None else settings.chat_base_url
    if not candidate:
        return None
    try:
        return await validate_chat_base_url(candidate)
    except UnsafeOutboundUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _recent_history(
    session: AsyncSession,
    conversation_id: UUID,
) -> list[ChatMessage]:
    limit = max(0, settings.chat_max_history_messages)
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


async def _sources_from_results(session: AsyncSession, results: list[dict]) -> list[ChatSource]:
    document_ids = {_as_uuid(row.get("document_id")) for row in results if row.get("document_id")}
    document_ids.discard(None)
    filenames: dict[str, str] = {}
    if document_ids:
        rows = await session.execute(
            sa.select(Document.id, Document.filename).where(Document.id.in_(document_ids))
        )
        filenames = {str(doc_id): filename for doc_id, filename in rows}

    sources: list[ChatSource] = []
    for row in results:
        cleaned = {key: value for key, value in row.items() if key != "embedding"}
        metadata = cleaned.get("metadata") if isinstance(cleaned.get("metadata"), dict) else {}
        document_id = str(cleaned["document_id"]) if cleaned.get("document_id") else None
        sources.append(
            ChatSource(
                id=str(cleaned.get("id") or len(sources) + 1),
                text=str(cleaned.get("text") or ""),
                score=float(cleaned.get("score") or 0.0),
                document_id=document_id,
                document_filename=filenames.get(document_id or ""),
                chunk_index=_int_or_none(cleaned.get("chunk_index")),
                page_no=_int_or_none(cleaned.get("page_no", metadata.get("page_no"))),
                char_start=_int_or_none(cleaned.get("char_start", metadata.get("char_start"))),
                char_end=_int_or_none(cleaned.get("char_end", metadata.get("char_end"))),
                metadata=metadata,
            )
        )
    return sources


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _model_messages(
    *,
    system_prompt: str,
    collection: str,
    sources: list[ChatSource],
    prior_messages: list[ChatMessage],
    user_message: str,
) -> list[dict[str, str]]:
    context = _context_block(sources)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": f'Retrieved context from collection "{collection}":\n\n{context}',
        },
    ]
    for message in prior_messages:
        if message.role not in {"user", "assistant"}:
            continue
        messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _context_block(sources: list[ChatSource]) -> str:
    if not sources:
        return "(no matching chunks were found)"
    remaining = max(1_000, settings.chat_max_context_chars)
    parts: list[str] = []
    for idx, source in enumerate(sources, start=1):
        label_parts = []
        if source.document_filename:
            label_parts.append(source.document_filename)
        if source.page_no is not None:
            label_parts.append(f"page {source.page_no}")
        label = f" ({', '.join(label_parts)})" if label_parts else ""
        prefix = f"[{idx}]{label} "
        budget = remaining - len(prefix) - 16
        if budget <= 0:
            break
        text = source.text[:budget]
        parts.append(f"{prefix}{text}")
        remaining -= len(prefix) + len(text)
    return "\n\n---\n\n".join(parts)


async def _complete_model(prepared: PreparedChatTurn) -> str:
    try:
        import openai
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="openai package is required for chat") from exc

    last_error: Exception | None = None
    for credential in prepared.credentials:
        client = _openai_client(openai, prepared, credential)
        try:
            response = await client.chat.completions.create(
                model=prepared.model,
                messages=prepared.model_messages,
                temperature=prepared.temperature,
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                return ""
            return getattr(choices[0].message, "content", None) or ""
        except Exception as exc:
            last_error = exc
            if not _should_try_next_credential(exc, prepared, credential):
                raise _provider_error(exc, credential) from exc
            logger.warning(
                "chat provider rejected credential, trying fallback",
                source=credential.source,
                error=_safe_chat_error(exc),
            )
        finally:
            await client.close()
    if last_error is not None:
        raise _provider_error(last_error, prepared.credentials[-1]) from last_error
    return ""


async def _stream_model(prepared: PreparedChatTurn) -> AsyncIterator[str]:
    try:
        import openai
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="openai package is required for chat") from exc

    last_error: Exception | None = None
    for credential in prepared.credentials:
        client = _openai_client(openai, prepared, credential)
        try:
            stream = await client.chat.completions.create(
                model=prepared.model,
                messages=prepared.model_messages,
                temperature=prepared.temperature,
                stream=True,
            )
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0].delta, "content", None)
                if delta:
                    yield delta
            return
        except Exception as exc:
            last_error = exc
            if not _should_try_next_credential(exc, prepared, credential):
                raise _provider_error(exc, credential) from exc
            logger.warning(
                "chat provider rejected credential, trying fallback",
                source=credential.source,
                error=_safe_chat_error(exc),
            )
        finally:
            await client.close()
    if last_error is not None:
        raise _provider_error(last_error, prepared.credentials[-1]) from last_error


def _openai_client(openai_module, prepared: PreparedChatTurn, credential: ProviderCredential):
    kwargs: dict[str, Any] = {"api_key": credential.api_key}
    if prepared.base_url:
        kwargs["base_url"] = prepared.base_url
    return openai_module.AsyncOpenAI(**kwargs)


def _should_try_next_credential(
    exc: Exception,
    prepared: PreparedChatTurn,
    credential: ProviderCredential,
) -> bool:
    if credential == prepared.credentials[-1]:
        return False
    return _is_provider_auth_error(exc)


def _is_provider_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return True
    message = str(exc).lower()
    return "invalid_api_key" in message or "incorrect api key" in message


def _provider_error(exc: Exception, credential: ProviderCredential) -> HTTPException:
    message = _safe_chat_error(exc)
    if _is_provider_auth_error(exc):
        message = (
            f"OpenAI rejected the {credential.source}. Save a fresh key in Chat settings "
            f"or clear the stale key. Upstream said: {message}"
        )
    return HTTPException(status_code=502, detail=message)


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
