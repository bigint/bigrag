from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.exceptions import ValidationError
from bigrag.ids import uuid7
from bigrag.models.chat import ChatCreateRequest, ChatTimings
from bigrag.services.chat.formatting import _chat_message_response
from bigrag.services.chat.turn.context import _model_messages
from bigrag.services.chat.turn.credentials import (
    _resolve_api_credentials,
    _resolve_base_url,
    _resolve_provider,
    assert_credentials_allowed_for_base_url,
)
from bigrag.services.chat.turn.sources import _sources_for_chat
from bigrag.services.chat.types import PreparedChatTurn
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_embedding_model_for, get_reranking_config
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.retrieval import retrieve
from bigrag.services.retrieval.fusion import tokenize_query
from bigrag.services.runtime_settings import get_values
from bigrag.services.tenant_enforcement import enforce_tenant_filters

_IDENTIFIER_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{11,}$", re.IGNORECASE)

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
    chat_filters = enforce_tenant_filters(collection, body.filters, user)
    provider = _resolve_provider(body.model_provider, runtime["chat_provider"])
    model = body.model or runtime["chat_model"]
    system_prompt = body.system_prompt or DEFAULT_SYSTEM_PROMPT
    multimodal = bool(body.multimodal and collection.get("multimodal_enabled"))
    top_k = max(1, min(int(body.top_k or collection.get("default_top_k") or 5), 100))
    requested_search_mode = body.search_mode or collection.get("default_search_mode", "semantic")
    search_mode = _effective_search_mode(requested_search_mode, body.message)
    min_score = (
        body.min_score if body.min_score is not None else collection.get("default_min_score")
    )
    rerank = body.rerank
    temperature = (
        body.temperature if body.temperature is not None else float(runtime["chat_temperature"])
    )
    credentials = await _resolve_api_credentials(session, user, body)
    base_url = await _resolve_base_url(body.provider_base_url, runtime["chat_base_url"])
    assert_credentials_allowed_for_base_url(
        credentials, base_url, request_base_url=body.provider_base_url
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
        filters=chat_filters,
        min_score=min_score,
        search_mode=search_mode,
        reranking_config=get_reranking_config(collection),
        rerank_override=rerank,
    )
    sources = await _sources_for_chat(
        session,
        collection=collection,
        message=body.message,
        filters=chat_filters,
        results=outcome.results,
    )
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
        "requested_search_mode": requested_search_mode,
        "min_score": min_score,
        "rerank": rerank,
        "multimodal": multimodal,
        "filters": chat_filters or {},
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

    model_messages = await _model_messages(
        system_prompt=system_prompt,
        collection=collection_name,
        sources=sources,
        user_message=body.message,
        max_context_chars=int(runtime["chat_max_context_chars"] or 120000),
        multimodal=multimodal,
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


def _effective_search_mode(search_mode: str, message: str) -> str:
    if search_mode != "semantic":
        return search_mode
    if any(_is_identifier_token(token) for token in tokenize_query(message)):
        return "hybrid"
    return search_mode


def _is_identifier_token(token: str) -> bool:
    return bool(_IDENTIFIER_TOKEN_RE.match(token)) and any(char.isdigit() for char in token)
