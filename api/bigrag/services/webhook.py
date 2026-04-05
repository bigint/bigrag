from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
import time
import uuid
from datetime import UTC, datetime

import httpx
import orjson

from bigrag.services.queue import IngestionEvent, event_bus
from bigrag.utils import safe_create_task

logger = logging.getLogger("bigrag.webhook")


def _retry_delays() -> list[int]:
    from bigrag.config import settings

    return settings.webhook_retry_delays


def _delivery_timeout() -> int:
    from bigrag.config import settings

    return settings.webhook_delivery_timeout


def _cache_ttl() -> int:
    from bigrag.config import settings

    return settings.webhook_cache_ttl


# Map ingestion event steps to webhook event names
_STEP_TO_EVENT = {
    "processing": "document.processing",
    "complete": "document.ready",
    "failed": "document.failed",
}


def generate_secret() -> str:
    """Generate a webhook signing secret."""
    return f"whsec_{secrets.token_urlsafe(32)}"


def compute_signature(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for a webhook payload."""
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _matches_webhook(webhook: dict, event: str, collection: str) -> bool:
    """Check if a webhook should receive this event."""
    if not webhook.get("active", True):
        return False
    if event not in webhook.get("events", []):
        return False
    collections = webhook.get("collections")
    if collections is not None and collection not in collections:
        return False
    return True


class WebhookDispatcher:
    """Subscribes to EventBus and dispatches webhooks for document state changes."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._task: asyncio.Task | None = None
        self._cache: list[dict] | None = None
        self._cache_time: float = 0

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=_delivery_timeout())
        self._task = asyncio.create_task(self._listen())
        logger.info("WebhookDispatcher started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
        logger.info("WebhookDispatcher stopped")

    def invalidate_cache(self) -> None:
        self._cache = None
        self._cache_time = 0

    async def _get_webhooks(self) -> list[dict]:
        """Fetch active webhooks with 60s in-memory cache."""
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < _cache_ttl():
            return self._cache

        from bigrag.database import db

        rows = await db.fetch("SELECT * FROM webhooks WHERE active = true")
        self._cache = [dict(r) for r in rows]
        self._cache_time = now
        return self._cache

    async def _listen(self) -> None:
        """Subscribe to all EventBus events and dispatch matching webhooks."""
        queue = event_bus.subscribe("*")
        try:
            while True:
                event = await queue.get()
                if event is None:
                    continue
                try:
                    await self._handle_event(event)
                except Exception as e:
                    logger.error(f"Error handling event: {e!r}")
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe("*", queue)

    async def _handle_event(self, event: IngestionEvent) -> None:
        """Match event to webhooks and dispatch deliveries."""
        webhook_event = _STEP_TO_EVENT.get(event.step)
        if webhook_event is None:
            return

        # Extract collection from event detail or look up from DB
        collection = event.detail.get("collection")
        if not collection:
            collection = await self._get_collection_for_document(event.document_id)
        if not collection:
            return

        webhooks = await self._get_webhooks()
        payload = self._build_payload(webhook_event, event, collection)

        for webhook in webhooks:
            if _matches_webhook(webhook, webhook_event, collection):
                safe_create_task(
                    self._deliver(webhook, webhook_event, payload),
                    name=f"webhook-deliver-{webhook['id']}",
                )

    async def _get_collection_for_document(self, document_id: str) -> str | None:
        """Look up the collection name for a document."""
        from bigrag.database import db

        row = await db.fetchrow(
            """
            SELECT c.name FROM documents d
            JOIN collections c ON c.id = d.collection_id
            WHERE d.id = $1
            """,
            uuid.UUID(document_id),
        )
        return row["name"] if row else None

    def _build_payload(self, webhook_event: str, event: IngestionEvent, collection: str) -> str:
        """Build the JSON payload for a webhook delivery."""
        data = {
            "event": webhook_event,
            "timestamp": datetime.now(UTC).isoformat(),
            "collection": collection,
            "document_id": event.document_id,
            "status": event.status,
            "chunk_count": event.detail.get("chunks", 0),
            "error_message": str(event.message) if event.status == "failed" else None,
        }
        return orjson.dumps(data).decode()

    async def _deliver(self, webhook: dict, event: str, payload: str) -> None:
        """Deliver a webhook with retries. Creates delivery record in DB."""
        from bigrag.database import db
        from bigrag.services.crypto import decrypt

        delivery_id = uuid.uuid4()
        webhook_id = webhook["id"]
        secret = decrypt(webhook["secret"])

        await db.execute(
            """
            INSERT INTO webhook_deliveries (id, webhook_id, event, payload, status)
            VALUES ($1, $2, $3, $4, 'pending')
            """,
            delivery_id,
            webhook_id,
            event,
            orjson.loads(payload),
        )

        signature = compute_signature(payload, secret)
        headers = {
            "Content-Type": "application/json",
            "X-BigRAG-Signature": signature,
            "X-BigRAG-Event": event,
            "X-BigRAG-Delivery": str(delivery_id),
            "User-Agent": "bigrag-webhooks/1.0",
        }

        last_error = None
        last_status_code = None

        retry_delays = _retry_delays()
        for attempt in range(1, len(retry_delays) + 2):  # 1 initial + 3 retries
            try:
                response = await self._client.post(
                    webhook["url"],
                    content=payload,
                    headers=headers,
                )
                last_status_code = response.status_code

                if 200 <= response.status_code < 300:
                    await db.execute(
                        """
                        UPDATE webhook_deliveries
                        SET status = 'delivered', attempts = $1,
                            last_status_code = $2, completed_at = now()
                        WHERE id = $3
                        """,
                        attempt,
                        last_status_code,
                        delivery_id,
                    )
                    logger.info(
                        f"Webhook delivered: webhook={webhook_id} event={event} "
                        f"delivery={delivery_id} attempt={attempt} status={last_status_code}"
                    )
                    return

                last_error = f"HTTP {response.status_code}"

            except Exception as e:
                last_error = str(e)

            # Update attempt count and schedule retry
            retry_index = attempt - 1
            if retry_index < len(retry_delays):
                delay = retry_delays[retry_index]
                logger.warning(
                    f"Webhook delivery failed: webhook={webhook_id} event={event} "
                    f"delivery={delivery_id} attempt={attempt} error={last_error} "
                    f"retrying_in={delay}s"
                )
                await db.execute(
                    """
                    UPDATE webhook_deliveries
                    SET attempts = $1, last_status_code = $2, last_error = $3,
                        next_retry_at = now() + interval '1 second' * $4
                    WHERE id = $5
                    """,
                    attempt,
                    last_status_code,
                    last_error,
                    delay,
                    delivery_id,
                )
                await asyncio.sleep(delay)
            else:
                break

        # All retries exhausted
        await db.execute(
            """
            UPDATE webhook_deliveries
            SET status = 'failed', attempts = $1,
                last_status_code = $2, last_error = $3, completed_at = now()
            WHERE id = $4
            """,
            len(retry_delays) + 1,
            last_status_code,
            last_error,
            delivery_id,
        )
        logger.error(
            f"Webhook delivery permanently failed: webhook={webhook_id} event={event} "
            f"delivery={delivery_id} error={last_error}"
        )

    async def deliver_test(self, webhook: dict) -> dict:
        """Send a test event to a webhook. Returns result inline (no retries)."""
        from bigrag.services.crypto import decrypt

        secret = decrypt(webhook["secret"])
        payload = orjson.dumps(
            {
                "event": "webhook.test",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ).decode()

        signature = compute_signature(payload, secret)
        headers = {
            "Content-Type": "application/json",
            "X-BigRAG-Signature": signature,
            "X-BigRAG-Event": "webhook.test",
            "X-BigRAG-Delivery": str(uuid.uuid4()),
            "User-Agent": "bigrag-webhooks/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=_delivery_timeout()) as client:
                response = await client.post(webhook["url"], content=payload, headers=headers)
            return {
                "status": "delivered" if 200 <= response.status_code < 300 else "failed",
                "status_code": response.status_code,
                "error": None
                if 200 <= response.status_code < 300
                else f"HTTP {response.status_code}",
            }
        except Exception as e:
            return {"status": "failed", "status_code": None, "error": str(e)}


webhook_dispatcher = WebhookDispatcher()
