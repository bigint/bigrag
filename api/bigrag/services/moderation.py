"""Content moderation via OpenAI's moderation endpoint.

Called from the upload path when a collection has ``moderation_enabled=
true``. A positive flag blocks ingestion with a 400 and an
``error_message`` explaining which category triggered. Without an
OpenAI API key we fail open with a warning so self-hosters on air-
gapped networks aren't silently blocked.
"""

from __future__ import annotations

import asyncio

from bigrag.logging import get_logger

logger = get_logger("bigrag.moderation")


async def check_text(text: str, api_key: str | None) -> tuple[bool, str | None]:
    """Return ``(flagged, reason_or_none)``.

    ``flagged=True`` → the caller should reject the upload.
    ``flagged=False, reason="unavailable"`` → moderation could not run
    (no key, API error). Policy on how to treat that is up to the
    caller — by default we fail open.
    """
    if not api_key:
        return False, "unavailable: no OpenAI api_key"
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key)
        resp = await asyncio.wait_for(
            client.moderations.create(input=text[:10_000]),
            timeout=10,
        )
        result = resp.results[0]
        if result.flagged:
            flagged_cats = [c for c, v in result.categories.model_dump().items() if v]
            return True, f"Flagged by moderation: {', '.join(flagged_cats)}"
        return False, None
    except Exception as exc:  # noqa: BLE001
        logger.warning("moderation: call failed, failing open", error=str(exc))
        return False, f"unavailable: {exc.__class__.__name__}"
