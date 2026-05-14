from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ChatConversation, ChatMessage, Document, UserPreference
from bigrag.exceptions import ServerError, ValidationError
from bigrag.models.chat import ChatCreateRequest, ChatSource, ChatTimings
from bigrag.routers.preferences import decrypt_preferences
from bigrag.services import crypto
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_embedding_model_for, get_reranking_config
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.retrieval import retrieve
from bigrag.services.runtime_settings import get_values
from bigrag.services.tenant_enforcement import require_tenant_filters
from bigrag.services.url_security import UnsafeOutboundUrlError, validate_chat_base_url

from .formatting import _as_uuid, _int_or_none, _title_from_message
from .history import _get_owned_conversation, _recent_history
from .types import PreparedChatTurn, ProviderCredential

_PROVIDERS = {"openai", "openai_compatible"}

DEFAULT_SYSTEM_PROMPT = (
    "You are bigRAG's grounded chat assistant. Answer using only the retrieved context. "
    "If the context does not contain the answer, say you do not know. Cite every factual "
    "claim with bracketed source numbers like [1] or [2]. Keep answers concise unless the "
    "user asks for detail."
)


async def _prepare_chat_turn(
    session: AsyncSession,
    user: dict,
    body: ChatCreateRequest,
) -> PreparedChatTurn:
    owner_id = UUID(user["id"])
    pinned = user.get("collection")
    runtime = await get_values(
        [
            "chat_provider",
            "chat_model",
            "chat_base_url",
            "chat_temperature",
            "chat_max_history_messages",
            "chat_max_context_chars",
        ]
    )

    if body.conversation_id is not None:
        conversation = await _get_owned_conversation(session, user, body.conversation_id)
        if (
            body.collection
            and conversation.collection_name
            and body.collection != conversation.collection_name
        ):
            raise ValidationError(
                "A conversation cannot switch collections. Start a new chat instead."
            )
        if not conversation.collection_name:
            raise ValidationError("Conversation is missing its collection")
        collection_name = conversation.collection_name
    else:
        collection_name = body.collection or pinned
        if not collection_name:
            raise ValidationError("collection is required")
        if pinned:
            assert_collection_matches_pin(pinned, collection_name)
        collection = await get_collection_or_404(collection_name)
        conversation = ChatConversation(
            owner_id=owner_id,
            title=_title_from_message(body.message),
            collection_id=collection.get("id"),
            collection_name=collection_name,
            model_provider=_resolve_provider(body.model_provider, runtime["chat_provider"]),
            model=body.model or runtime["chat_model"],
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
            else runtime["chat_temperature"],
        )
        session.add(conversation)
        await session.flush()

    collection = await get_collection_or_404(collection_name)
    require_tenant_filters(collection, body.filters)
    _apply_turn_overrides(conversation, body, collection, runtime["chat_provider"])
    provider = _resolve_provider(conversation.model_provider, runtime["chat_provider"])
    credentials = await _resolve_api_credentials(session, user, body)
    base_url = await _resolve_base_url(body.provider_base_url, runtime["chat_base_url"])

    prior_messages = await _recent_history(
        session,
        conversation.id,
        int(runtime["chat_max_history_messages"] or 0),
    )

    try:
        embedding_model = get_embedding_model_for(collection)
    except (ImportError, ValueError, ValidationError) as exc:
        raise ValidationError(str(exc)) from exc

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
        max_context_chars=int(runtime["chat_max_context_chars"] or 120000),
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


def _resolve_provider(provider: str | None, default_provider: str | None = "openai") -> str:
    value = (provider or default_provider or "openai").strip().lower()
    if value not in _PROVIDERS:
        raise ValidationError("Only openai and openai_compatible chat providers are supported")
    return value


def _apply_turn_overrides(
    conversation: ChatConversation,
    body: ChatCreateRequest,
    collection: dict,
    default_provider: str | None,
) -> None:
    if body.model_provider is not None:
        conversation.model_provider = _resolve_provider(body.model_provider, default_provider)
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
    _append_credential(credentials, chat.get("openai_key"), "saved chat key")

    if not credentials:
        raise ValidationError(
            "Save an OpenAI API key in Chat settings, or pass provider_api_key "
            "with the chat request."
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
        raise ServerError(f"{source} cannot be decrypted. Configure BIGRAG_MASTER_KEY.")
    if any(existing.api_key == api_key for existing in credentials):
        return
    credentials.append(ProviderCredential(api_key=api_key, source=source))


async def _resolve_base_url(raw_base_url: str | None, default_base_url: str | None) -> str | None:
    candidate = raw_base_url if raw_base_url is not None else default_base_url
    if not candidate:
        return None
    try:
        return await validate_chat_base_url(candidate)
    except UnsafeOutboundUrlError as exc:
        raise ValidationError(str(exc)) from exc


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


def _model_messages(
    *,
    system_prompt: str,
    collection: str,
    sources: list[ChatSource],
    prior_messages: list[ChatMessage],
    user_message: str,
    max_context_chars: int,
) -> list[dict[str, str]]:
    context = _context_block(sources, max_context_chars)
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


def _context_block(sources: list[ChatSource], max_context_chars: int) -> str:
    if not sources:
        return "(no matching chunks were found)"
    remaining = max(1_000, max_context_chars)
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


async def _clear_saved_chat_key(session: AsyncSession, user: dict) -> None:
    user_id = UUID(user["id"])
    data = await session.scalar(
        sa.select(UserPreference.data).where(UserPreference.user_id == user_id)
    )
    if not isinstance(data, dict):
        return
    chat = data.get("chat")
    if not isinstance(chat, dict) or "openai_key" not in chat:
        return
    cleaned_chat = {**chat}
    cleaned_chat.pop("openai_key", None)
    cleaned = {**data, "chat": cleaned_chat}
    await session.execute(
        sa.update(UserPreference)
        .where(UserPreference.user_id == user_id)
        .values(data=cleaned, updated_at=sa.func.now())
    )
    await session.commit()
