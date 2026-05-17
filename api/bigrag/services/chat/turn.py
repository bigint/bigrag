from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, UserPreference
from bigrag.exceptions import ServerError, ValidationError
from bigrag.ids import uuid7
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

from .formatting import _as_uuid, _chat_message_response, _int_or_none
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
    pinned = user.get("collection")
    runtime = await get_values(
        [
            "chat_provider",
            "chat_model",
            "chat_base_url",
            "chat_temperature",
            "chat_max_context_chars",
        ]
    )

    collection_name = body.collection
    if pinned:
        assert_collection_matches_pin(pinned, collection_name)
    collection = await get_collection_or_404(collection_name)
    require_tenant_filters(collection, body.filters)
    provider = _resolve_provider(body.model_provider, runtime["chat_provider"])
    model = body.model or runtime["chat_model"]
    system_prompt = body.system_prompt or DEFAULT_SYSTEM_PROMPT
    top_k = max(1, min(int(body.top_k or collection.get("default_top_k") or 5), 100))
    search_mode = body.search_mode or collection.get("default_search_mode", "semantic")
    min_score = (
        body.min_score if body.min_score is not None else collection.get("default_min_score")
    )
    rerank = body.rerank
    temperature = (
        body.temperature if body.temperature is not None else float(runtime["chat_temperature"])
    )
    credentials = await _resolve_api_credentials(session, user, body)
    base_url = await _resolve_base_url(body.provider_base_url, runtime["chat_base_url"])
    if body.provider_base_url is not None and any(
        cred.source == "instance chat key" for cred in credentials
    ):
        raise ValidationError(
            "provider_base_url requires provider_api_key or a saved chat key; "
            "the instance chat key cannot be sent to a custom base URL."
        )
    if (
        base_url is not None
        and not base_url.rstrip("/").startswith("https://api.openai.com")
        and any(cred.source == "instance chat key" for cred in credentials)
    ):
        raise ValidationError(
            "The instance chat key cannot be sent to a non-default chat base URL; "
            "save a chat key in Chat settings or pass provider_api_key."
        )

    try:
        embedding_model = get_embedding_model_for(collection)
    except (ImportError, ValueError, ValidationError) as exc:
        raise ValidationError(str(exc)) from exc

    outcome = await retrieve(
        collection_name=collection_name,
        query=body.message,
        embedding_model=embedding_model,
        top_k=top_k,
        filters=body.filters,
        min_score=min_score,
        search_mode=search_mode,
        reranking_config=get_reranking_config(collection),
        rerank_override=rerank,
        vector_store_provider=collection.get("vector_store_provider"),
    )
    sources = await _sources_from_results(session, outcome.results)
    timings = ChatTimings(
        embed_ms=outcome.embed_ms,
        search_ms=outcome.search_ms,
        rerank_ms=outcome.rerank_ms,
        cache_ms=outcome.cache_ms,
        total_ms=outcome.total_ms,
        cache_hit=outcome.cache_hit,
    )
    retrieval = {
        "collection": collection_name,
        "query": body.message,
        "top_k": top_k,
        "search_mode": search_mode,
        "min_score": min_score,
        "rerank": rerank,
        "filters": body.filters or {},
        "sources": [source.model_dump(mode="json") for source in sources],
        "timings": timings.model_dump(mode="json"),
    }

    user_message = _chat_message_response(
        id=str(uuid7()),
        role="user",
        content=body.message,
        retrieval={},
        created_at=datetime.now(UTC),
    )

    model_messages = _model_messages(
        system_prompt=system_prompt,
        collection=collection_name,
        sources=sources,
        user_message=body.message,
        max_context_chars=int(runtime["chat_max_context_chars"] or 120000),
    )
    return PreparedChatTurn(
        collection=collection_name,
        user_message=user_message,
        model_messages=model_messages,
        sources=sources,
        timings=timings,
        retrieval=retrieval,
        model_provider=provider,
        model=model,
        temperature=temperature,
        credentials=credentials,
        base_url=base_url,
    )


def _resolve_provider(provider: str | None, default_provider: str | None = "openai") -> str:
    value = (provider or default_provider or "openai").strip().lower()
    if value not in _PROVIDERS:
        raise ValidationError("Only openai and openai_compatible chat providers are supported")
    return value


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
        env_key = os.environ.get("BIGRAG_CHAT_API_KEY")
        _append_credential(credentials, env_key, "instance chat key")

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
        msg = f"{source} cannot be decrypted. Configure BIGRAG_MASTER_KEY."
        raise ServerError(msg, public_message=msg)
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
    user_message: str,
    max_context_chars: int,
) -> list[dict[str, str]]:
    context = _context_block(sources, max_context_chars)
    combined_system = (
        f'{system_prompt}\n\nRetrieved context from collection "{collection}":\n\n{context}'
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": combined_system},
        {"role": "user", "content": user_message},
    ]
    return messages


def _context_block(sources: list[ChatSource], max_context_chars: int) -> str:
    if not sources:
        return "(no matching chunks were found)"
    remaining = max(100, min(max_context_chars, 200_000))
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
