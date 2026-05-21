from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, DocumentElement
from bigrag.exceptions import ValidationError
from bigrag.ids import uuid7
from bigrag.models.chat import ChatCreateRequest, ChatSource, ChatTimings
from bigrag.services.chat.formatting import _as_uuid, _chat_message_response, _int_or_none
from bigrag.services.chat.turn.credentials import (
    _resolve_api_credentials,
    _resolve_base_url,
    _resolve_provider,
    assert_credentials_allowed_for_base_url,
)
from bigrag.services.chat.types import PreparedChatTurn
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_embedding_model_for, get_reranking_config
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.document_elements import element_ref
from bigrag.services.multimodal_assets import image_content_parts_for_refs
from bigrag.services.retrieval import retrieve
from bigrag.services.runtime_settings import get_values
from bigrag.services.tenant_enforcement import require_tenant_filters

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
    multimodal = bool(body.multimodal and collection.get("multimodal_enabled"))
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
        "multimodal": multimodal,
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


async def _sources_from_results(session: AsyncSession, results: list[dict]) -> list[ChatSource]:
    document_ids = {_as_uuid(row.get("document_id")) for row in results if row.get("document_id")}
    document_ids.discard(None)
    filenames: dict[str, str] = {}
    if document_ids:
        rows = await session.execute(
            sa.select(Document.id, Document.filename).where(Document.id.in_(document_ids))
        )
        filenames = {str(doc_id): filename for doc_id, filename in rows}

    hydrated_refs = await _hydrated_element_refs(session, results)
    sources: list[ChatSource] = []
    for row in results:
        cleaned = {key: value for key, value in row.items() if key != "embedding"}
        metadata = cleaned.get("metadata") if isinstance(cleaned.get("metadata"), dict) else {}
        multimodal_elements = hydrated_refs.get(str(cleaned.get("id"))) or metadata.get(
            "multimodal_elements"
        )
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
                multimodal_elements=multimodal_elements
                if isinstance(multimodal_elements, list)
                else [],
                metadata=metadata,
            )
        )
    return sources


async def _hydrated_element_refs(
    session: AsyncSession,
    results: list[dict],
) -> dict[str, list[dict[str, Any]]]:
    pairs = []
    by_result: dict[str, list[tuple[str, int]]] = {}
    for row in results:
        result_id = str(row.get("id") or "")
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        refs = metadata.get("multimodal_elements")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            raw_document_id = ref.get("document_id") or row.get("document_id")
            raw_index = ref.get("element_index")
            if raw_document_id is None or raw_index is None:
                continue
            doc_uuid = _as_uuid(raw_document_id)
            try:
                element_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if doc_uuid is None:
                continue
            key = (str(doc_uuid), element_index)
            pairs.append(key)
            by_result.setdefault(result_id, []).append(key)
    if not pairs:
        return {}
    rows = (
        await session.scalars(
            sa.select(DocumentElement).where(
                sa.tuple_(DocumentElement.document_id, DocumentElement.element_index).in_(
                    {(_as_uuid(doc_id), index) for doc_id, index in pairs}
                )
            )
        )
    ).all()
    hydrated = {
        (str(row.document_id), row.element_index): element_ref(
            row, document_id=str(row.document_id)
        )
        for row in rows
    }
    return {
        result_id: [hydrated[key] for key in keys if key in hydrated]
        for result_id, keys in by_result.items()
    }


async def _model_messages(
    *,
    system_prompt: str,
    collection: str,
    sources: list[ChatSource],
    user_message: str,
    max_context_chars: int,
    multimodal: bool,
) -> list[dict[str, Any]]:
    context = _context_block(sources, max_context_chars, include_elements=multimodal)
    combined_system = (
        f'{system_prompt}\n\nRetrieved context from collection "{collection}":\n\n{context}'
    )
    user_content: str | list[dict[str, Any]] = user_message
    if multimodal:
        refs = [
            ref.model_dump(mode="json") for source in sources for ref in source.multimodal_elements
        ]
        image_parts = await image_content_parts_for_refs(refs)
        if image_parts:
            user_content = [{"type": "text", "text": user_message}, *image_parts]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": combined_system},
        {"role": "user", "content": user_content},
    ]
    return messages


def _context_block(
    sources: list[ChatSource],
    max_context_chars: int,
    *,
    include_elements: bool,
) -> str:
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
        element_text = _source_element_context(source) if include_elements else ""
        parts.append(f"{prefix}{text}{element_text}")
        remaining -= len(prefix) + len(text) + len(element_text)
    return "\n\n---\n\n".join(parts)


def _source_element_context(source: ChatSource) -> str:
    if not source.multimodal_elements:
        return ""
    lines = []
    for element in source.multimodal_elements[:5]:
        detail = element.summary or element.caption or element.text
        if detail:
            lines.append(f"- {element.kind}: {detail[:600]}")
        else:
            lines.append(f"- {element.kind}")
    return "\n\nRetrieved elements:\n" + "\n".join(lines)
