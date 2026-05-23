from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import DocumentElement
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.runtime_settings import get_values
from bigrag.services.url_security import (
    UnsafeOutboundUrlError,
    pin_chat_base_url,
    pinned_async_client,
)

ENRICHABLE_KINDS = {"image", "table", "equation"}
MAX_ELEMENTS_PER_RUN = 25
MAX_SUMMARY_CHARS = 4000
MODEL_TIMEOUT_SECONDS = 60


async def enrich_document_elements(document_id: str | uuid.UUID) -> int:
    try:
        import openai
    except ImportError as exc:
        await mark_document_enrichment_failed(document_id, "openai package is required")
        raise RuntimeError("openai package is required") from exc

    api_key = os.environ.get("BIGRAG_CHAT_API_KEY")
    if not api_key:
        await mark_document_enrichment_failed(
            document_id,
            "Configure BIGRAG_CHAT_API_KEY to enable multimodal enrichment.",
        )
        return 0

    runtime = await get_values(["chat_model", "chat_base_url", "chat_temperature"])
    base_url = runtime["chat_base_url"] or "https://api.openai.com/v1"
    try:
        pinned = await pin_chat_base_url(base_url)
    except UnsafeOutboundUrlError as exc:
        await mark_document_enrichment_failed(
            document_id,
            "Chat provider URL was rejected by SSRF protection.",
        )
        raise RuntimeError(str(exc)) from exc

    client = openai.AsyncOpenAI(
        api_key=api_key.strip(),
        base_url=base_url,
        timeout=MODEL_TIMEOUT_SECONDS,
        http_client=pinned_async_client(pinned, timeout=MODEL_TIMEOUT_SECONDS),
    )
    try:
        return await _enrich_with_client(
            document_id,
            client=client,
            model=runtime["chat_model"],
            temperature=float(runtime["chat_temperature"]),
        )
    finally:
        await client.close()


async def mark_document_enrichment_failed(document_id: str | uuid.UUID, message: str) -> None:
    safe = sanitize_message_text(message) or "multimodal enrichment failed"
    doc_id = uuid.UUID(str(document_id))
    async with session_factory()() as session:
        await session.execute(
            sa.update(DocumentElement)
            .where(DocumentElement.document_id == doc_id)
            .where(DocumentElement.enrichment_status == "pending")
            .values(enrichment_status="failed", enrichment_error=safe)
        )
        await session.commit()


async def _enrich_with_client(
    document_id: str | uuid.UUID,
    *,
    client: Any,
    model: str,
    temperature: float,
) -> int:
    doc_id = uuid.UUID(str(document_id))
    async with session_factory()() as session:
        rows = (
            await session.scalars(
                sa.select(DocumentElement)
                .where(DocumentElement.document_id == doc_id)
                .where(DocumentElement.kind.in_(ENRICHABLE_KINDS))
                .where(DocumentElement.enrichment_status == "pending")
                .order_by(DocumentElement.element_index.asc())
                .limit(MAX_ELEMENTS_PER_RUN)
            )
        ).all()
        enriched = 0
        for row in rows:
            prompt = _prompt_for_element(row)
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": content}],
                    temperature=temperature,
                ),
                timeout=MODEL_TIMEOUT_SECONDS,
            )
            choices = getattr(response, "choices", None) or []
            summary = ""
            if choices:
                summary = getattr(choices[0].message, "content", None) or ""
            row.summary = sanitize_message_text(summary)[:MAX_SUMMARY_CHARS]
            row.enrichment_status = "ready"
            row.enrichment_error = None
            enriched += 1
        await session.commit()
        return enriched


def _prompt_for_element(row: DocumentElement) -> str:
    parts = [
        "Summarize this retrieved document element for grounded retrieval.",
        f"Element kind: {row.kind}",
    ]
    if row.caption:
        parts.append(f"Caption: {row.caption}")
    if row.text:
        parts.append(f"Extracted text:\n{row.text[:8000]}")
    if row.surrounding_context:
        parts.append(f"Nearby context:\n{row.surrounding_context[:2000]}")
    return "\n\n".join(parts)
