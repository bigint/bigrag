from __future__ import annotations

import asyncio

from bigrag.logging import get_logger

logger = get_logger("bigrag.moderation")


async def check_text(text: str, api_key: str | None) -> tuple[bool, str | None]:

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
