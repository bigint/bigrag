from __future__ import annotations

import asyncio
import hashlib
import hmac
import random
import secrets
import time
import uuid
from datetime import UTC, datetime

import httpx
import orjson

from bigrag.logging import get_logger
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.webhook")


def _retry_delays() -> list[int]:
    from bigrag.config import settings

    return settings.webhook_retry_delays


def _delivery_timeout() -> int:
    from bigrag.config import settings

    return settings.webhook_delivery_timeout


def _cache_ttl() -> int:
    from bigrag.config import settings

    return settings.webhook_cache_ttl


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


def _jittered_delay(base_delay: int, jitter_factor: float = 0.25) -> float:
    """Add ±25% jitter to a delay to avoid thundering herd."""
    jitter = base_delay * jitter_factor
    return base_delay + random.uniform(-jitter, jitter)


class CircuitBreaker:
    """Per-webhook circuit breaker to avoid retry storms against a down endpoint."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 300) -> None:
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown_seconds
        # webhook_id -> (consecutive_failures, last_failure_time)
        self._state: dict[str, tuple[int, float]] = {}

    def is_open(self, webhook_id: str) -> bool:
        """Return True if circuit is open (should NOT deliver)."""
        state = self._state.get(webhook_id)
        if state is None:
            return False
        failures, last_failure = state
        if failures >= self._failure_threshold:
            if time.monotonic() - last_failure < self._cooldown:
                return True
            # Cooldown expired, allow one attempt (half-open)
            return False
        return False

    def record_success(self, webhook_id: str) -> None:
        self._state.pop(webhook_id, None)

    def record_failure(self, webhook_id: str) -> None:
        state = self._state.get(webhook_id)
        if state:
            failures, _ = state
            self._state[webhook_id] = (failures + 1, time.monotonic())
        else:
            self._state[webhook_id] = (1, time.monotonic())


class WebhookDispatcher:
    """Subscribes to EventBus and dispatches webhooks for document state changes."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._task: asyncio.Task | None = None
        self._circuit_breaker = CircuitBreaker()
        # Per-webhook concurrency limiter (max 5 concurrent deliveries per webhook)
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, webhook_id: str) -> asyncio.Semaphore:
        if webhook_id not in self._semaphores:
            self._semaphores[webhook_id] = asyncio.Semaphore(5)
        return self._semaphores[webhook_id]

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

    async def invalidate_cache(self) -> None:
        from bigrag.services import redis_cache

        await redis_cache.delete("webhooks:active")

    async def _get_webhooks(self) -> list[dict]:
        """Fetch active webhooks, cached in Redis."""
        from bigrag.services import redis_cache

        cached = await redis_cache.get("webhooks:active")
        if cached is not None:
            return cached

        import sqlalchemy as sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import Webhook

        async with session_factory()() as session:
            rows = (await session.scalars(sa.select(Webhook).where(Webhook.active.is_(True)))).all()
        webhooks = [
            {
                "id": str(w.id),
                "url": w.url,
                "secret": w.secret,
                "events": list(w.events),
                "collections": list(w.collections) if w.collections else None,
                "description": w.description,
                "active": w.active,
                "created_by": str(w.created_by) if w.created_by else None,
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat(),
            }
            for w in rows
        ]
        await redis_cache.set("webhooks:active", webhooks, ttl=_cache_ttl())
        return webhooks

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
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error handling event: {e!r}")
        finally:
            event_bus.unsubscribe("*", queue)

    async def _handle_event(self, event: IngestionEvent) -> None:
        """Match event to webhooks and dispatch deliveries."""
        webhook_event = _STEP_TO_EVENT.get(event.step)
        if webhook_event is None:
            return

        collection = event.detail.get("collection")
        if not collection:
            collection = await self._get_collection_for_document(event.document_id)
        if not collection:
            return

        webhooks = await self._get_webhooks()
        payload = self._build_payload(webhook_event, event, collection)

        for webhook in webhooks:
            if _matches_webhook(webhook, webhook_event, collection):
                wh_id = str(webhook["id"])

                if self._circuit_breaker.is_open(wh_id):
                    logger.warning(
                        f"Circuit open for webhook={wh_id}, skipping delivery for {webhook_event}"
                    )
                    continue

                safe_create_task(
                    self._deliver(webhook, webhook_event, payload),
                    name=f"webhook-deliver-{wh_id}",
                )

    async def _get_collection_for_document(self, document_id: str) -> str | None:
        """Look up the collection name for a document."""
        import sqlalchemy as sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import Collection, Document

        async with session_factory()() as session:
            name = await session.scalar(
                sa.select(Collection.name)
                .join(Document, Document.collection_id == Collection.id)
                .where(Document.id == uuid.UUID(document_id))
            )
        return name

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
        """Deliver a webhook with retries, circuit breaker, and jitter."""
        import sqlalchemy as sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import WebhookDelivery

        webhook_id = webhook["id"]
        wh_id_uuid = uuid.UUID(webhook_id) if isinstance(webhook_id, str) else webhook_id
        wh_id_str = str(webhook_id)
        sem = self._get_semaphore(wh_id_str)

        async with sem:
            delivery_id = uuid.uuid4()
            secret = webhook["secret"]

            async with session_factory()() as session:
                session.add(
                    WebhookDelivery(
                        id=delivery_id,
                        webhook_id=wh_id_uuid,
                        event=event,
                        payload=orjson.loads(payload),
                        status="pending",
                    )
                )
                await session.commit()

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

            # Re-validate URL target at delivery time to prevent DNS rebinding
            try:
                from bigrag.models.webhook import resolve_and_validate_url

                resolve_and_validate_url(webhook["url"])
            except ValueError as e:
                logger.warning(
                    f"Webhook blocked: webhook={webhook_id} url={webhook['url']} reason={e}"
                )
                async with session_factory()() as session:
                    await session.execute(
                        sa.update(WebhookDelivery)
                        .where(WebhookDelivery.id == delivery_id)
                        .values(
                            status="failed",
                            attempts=1,
                            last_error="Blocked: URL targets a private or internal network",
                            completed_at=sa.func.now(),
                        )
                    )
                    await session.commit()
                return

            retry_delays = _retry_delays()
            for attempt in range(1, len(retry_delays) + 2):  # 1 initial + N retries
                # Re-validate the URL on every attempt. Retry delays can
                # stretch into minutes, and an attacker who controls DNS
                # for the webhook target could flip the record to a private
                # IP between attempts.
                if attempt > 1:
                    try:
                        from bigrag.models.webhook import resolve_and_validate_url

                        resolve_and_validate_url(webhook["url"])
                    except ValueError as exc:
                        last_error = f"Blocked: {exc}"
                        break

                try:
                    response = await self._client.post(
                        webhook["url"],
                        content=payload,
                        headers=headers,
                    )
                    last_status_code = response.status_code

                    if 200 <= response.status_code < 300:
                        async with session_factory()() as session:
                            await session.execute(
                                sa.update(WebhookDelivery)
                                .where(WebhookDelivery.id == delivery_id)
                                .values(
                                    status="delivered",
                                    attempts=attempt,
                                    last_status_code=last_status_code,
                                    completed_at=sa.func.now(),
                                )
                            )
                            await session.commit()
                        self._circuit_breaker.record_success(wh_id_str)
                        logger.info(
                            f"Webhook delivered: webhook={webhook_id} event={event} "
                            f"delivery={delivery_id} attempt={attempt} status={last_status_code}"
                        )
                        return

                    last_error = f"HTTP {response.status_code}"

                except Exception as e:
                    last_error = str(e)

                retry_index = attempt - 1
                if retry_index < len(retry_delays):
                    delay = _jittered_delay(retry_delays[retry_index])
                    logger.warning(
                        f"Webhook delivery failed: webhook={webhook_id} event={event} "
                        f"delivery={delivery_id} attempt={attempt} error={last_error} "
                        f"retrying_in={delay:.1f}s"
                    )
                    async with session_factory()() as session:
                        await session.execute(
                            sa.update(WebhookDelivery)
                            .where(WebhookDelivery.id == delivery_id)
                            .values(
                                attempts=attempt,
                                last_status_code=last_status_code,
                                last_error=last_error,
                                next_retry_at=sa.func.now()
                                + sa.text("make_interval(secs => :s)").bindparams(s=int(delay)),
                            )
                        )
                        await session.commit()
                    await asyncio.sleep(delay)
                else:
                    break

            self._circuit_breaker.record_failure(wh_id_str)
            async with session_factory()() as session:
                await session.execute(
                    sa.update(WebhookDelivery)
                    .where(WebhookDelivery.id == delivery_id)
                    .values(
                        status="failed",
                        attempts=len(retry_delays) + 1,
                        last_status_code=last_status_code,
                        last_error=last_error,
                        completed_at=sa.func.now(),
                    )
                )
                await session.commit()
            logger.error(
                f"Webhook delivery permanently failed: webhook={webhook_id} event={event} "
                f"delivery={delivery_id} error={last_error}"
            )

    async def deliver_once(self, webhook: dict, event: str, payload: str) -> dict:
        """Fire a single one-off delivery (no retries, no circuit-breaker
        state touched). Used by the admin replay endpoint.

        Returns a dict shaped like :meth:`deliver_test`'s result so the
        Studio UI can render both the same way.
        """
        try:
            from bigrag.models.webhook import resolve_and_validate_url

            resolve_and_validate_url(webhook["url"])
        except ValueError:
            return {
                "status": "failed",
                "status_code": None,
                "error": "Blocked: URL targets a private or internal network",
            }

        signature = compute_signature(payload, webhook["secret"])
        headers = {
            "Content-Type": "application/json",
            "X-BigRAG-Signature": signature,
            "X-BigRAG-Event": event,
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
        except Exception as exc:  # noqa: BLE001 — surface connect errors to the UI
            return {
                "status": "failed",
                "status_code": None,
                "error": f"{exc.__class__.__name__}: {exc}",
            }

    async def deliver_test(self, webhook: dict) -> dict:
        """Send a test event to a webhook. Returns result inline (no retries)."""
        # Re-validate URL target at delivery time to prevent DNS rebinding
        try:
            from bigrag.models.webhook import resolve_and_validate_url

            resolve_and_validate_url(webhook["url"])
        except ValueError:
            return {
                "status": "failed",
                "status_code": None,
                "error": "Blocked: URL targets a private or internal network",
            }

        secret = webhook["secret"]
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
        except Exception:
            return {"status": "failed", "status_code": None, "error": "Connection failed"}


webhook_dispatcher = WebhookDispatcher()
