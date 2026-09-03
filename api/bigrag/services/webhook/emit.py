from __future__ import annotations

from bigrag.logging import get_logger
from bigrag.services.webhook.dispatcher import webhook_dispatcher

logger = get_logger("bigrag.webhook")


async def enqueue_webhook_event(
    event: str,
    *,
    collection: str | None = None,
    data: dict | None = None,
) -> int:
    try:
        return await webhook_dispatcher.enqueue_event(event, collection=collection, data=data)
    except Exception as exc:
        logger.warning(
            "webhook event enqueue failed",
            webhook_event=event,
            collection=collection,
            error=repr(exc),
        )
        return 0
