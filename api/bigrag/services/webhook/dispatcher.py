from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import orjson

from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.webhook.signing import compute_signature

logger = get_logger("bigrag.webhook")
_RNG = secrets.SystemRandom()


def _retry_delays() -> list[int]:
    from bigrag.services.runtime_settings import sync_value

    return sync_value("webhook_retry_delays")


def _delivery_timeout() -> int:
    from bigrag.services.runtime_settings import sync_value

    return sync_value("webhook_delivery_timeout")


_STEP_TO_EVENT = {
    "processing": "document.processing",
    "complete": "document.ready",
    "failed": "document.failed",
}


def _matches_webhook(webhook: dict, event: str, collection: str) -> bool:
    if not webhook.get("active", True):
        return False
    if event not in webhook.get("events", []):
        return False
    collections = webhook.get("collections")
    if collections is not None and collection not in collections:
        return False
    return True


def _jittered_delay(base_delay: int, jitter_factor: float = 0.25) -> float:
    jitter = base_delay * jitter_factor
    return base_delay + _RNG.uniform(-jitter, jitter)


class WebhookDispatcher:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, webhook_id: str) -> asyncio.Semaphore:
        if webhook_id not in self._semaphores:
            self._semaphores[webhook_id] = asyncio.Semaphore(5)
        return self._semaphores[webhook_id]

    async def start(self) -> None:
        logger.info("WebhookDispatcher started")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
        logger.info("WebhookDispatcher stopped")

    async def _post_pinned(
        self,
        url: str,
        payload: str,
        headers: dict[str, str],
    ) -> httpx.Response:
        from bigrag.services.runtime_settings import get_value
        from bigrag.services.url_security import pinned_async_client, resolve_and_pin

        allow_local = await get_value("allow_local_webhooks")
        timeout = _delivery_timeout()
        pinned = await resolve_and_pin(
            url,
            purpose="Webhook URL",
            allow_loopback=allow_local,
            allow_private=allow_local,
        )
        async with pinned_async_client(
            pinned,
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            response = await client.post(url, content=payload, headers=headers)
            _ = response.status_code
            await response.aclose()
            return response

    async def _get_webhooks(self) -> list[dict]:
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
        return webhooks

    async def _listen(self) -> None:
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
                except Exception as exc:
                    logger.error("error handling webhook event", error=repr(exc))
        finally:
            event_bus.unsubscribe("*", queue)

    async def _handle_event(self, event: IngestionEvent) -> None:
        webhook_event = _STEP_TO_EVENT.get(event.step)
        if webhook_event is None:
            return

        collection = event.collection_name
        if not collection and event.document_id:
            collection = await self._get_collection_for_document(event.document_id)
        if not collection:
            return

        webhooks = await self._get_webhooks()
        payload = self._build_payload(webhook_event, event, collection)

        for webhook in webhooks:
            if _matches_webhook(webhook, webhook_event, collection):
                await self._deliver(webhook, webhook_event, payload)

    async def _get_collection_for_document(self, document_id: str) -> str | None:
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
        from bigrag.services.error_sanitize import sanitize_message_text

        data = {
            "event": webhook_event,
            "timestamp": datetime.now(UTC).isoformat(),
            "collection": collection,
            "document_id": event.document_id,
            "status": event.status,
            "chunk_count": event.detail.get("chunks", 0),
            "error_message": sanitize_message_text(str(event.message))
            if event.status == "failed"
            else None,
        }
        return orjson.dumps(data).decode()

    async def _deliver(self, webhook: dict, event: str, payload: str) -> None:
        from bigrag.db.engine import session_factory
        from bigrag.db.models import WebhookDelivery

        webhook_id = webhook["id"]
        wh_id_uuid = uuid.UUID(webhook_id) if isinstance(webhook_id, str) else webhook_id
        delivery_id = uuid7()

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

        from bigrag.services.jobs.actors import enqueue_webhook_outbox

        enqueue_webhook_outbox(delivery_id=str(delivery_id))

    async def process_due_deliveries(
        self,
        *,
        delivery_id: uuid.UUID | None = None,
        limit: int = 25,
    ) -> int:
        import sqlalchemy as sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import Webhook, WebhookDelivery

        retry_delays = _retry_delays()
        max_attempts = len(retry_delays) + 1
        claim_seconds = max(max(_delivery_timeout(), 1) * 2, 60)

        async with session_factory()() as session:
            stmt = (
                sa.select(WebhookDelivery, Webhook)
                .join(Webhook, Webhook.id == WebhookDelivery.webhook_id)
                .where(WebhookDelivery.status == "pending")
                .where(
                    sa.or_(
                        WebhookDelivery.next_retry_at.is_(None),
                        WebhookDelivery.next_retry_at <= sa.func.now(),
                    )
                )
                .order_by(WebhookDelivery.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            if delivery_id is not None:
                stmt = stmt.where(WebhookDelivery.id == delivery_id)
            rows = (await session.execute(stmt)).all()
            work = []
            for delivery, webhook in rows:
                attempt = int(delivery.attempts or 0) + 1
                delivery.attempts = attempt
                delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=claim_seconds)
                work.append(
                    {
                        "attempt": attempt,
                        "delivery_id": delivery.id,
                        "event": delivery.event,
                        "payload": orjson.dumps(delivery.payload).decode(),
                        "webhook": {
                            "id": webhook.id,
                            "url": webhook.url,
                            "secret": webhook.secret,
                        },
                    }
                )
            await session.commit()

        groups: dict[str, list[dict]] = {}
        for item in work:
            groups.setdefault(str(item["webhook"]["id"]), []).append(item)

        async def _process_group(items: list[dict]) -> None:
            await asyncio.gather(
                *[
                    self._attempt_delivery(
                        item["webhook"],
                        item["event"],
                        item["payload"],
                        item["delivery_id"],
                        item["attempt"],
                        retry_delays,
                        max_attempts,
                    )
                    for item in items
                ]
            )

        await asyncio.gather(*[_process_group(items) for items in groups.values()])
        return len(work)

    async def _attempt_delivery(
        self,
        webhook: dict,
        event: str,
        payload: str,
        delivery_id: uuid.UUID,
        attempt: int,
        retry_delays: list[int],
        max_attempts: int,
    ) -> None:
        import sqlalchemy as sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import WebhookDelivery

        webhook_id = str(webhook["id"])
        sem = self._get_semaphore(webhook_id)
        last_error = None
        last_status_code = None
        delivered = False
        terminal = False

        async with sem:
            try:
                timestamp = str(int(datetime.now(UTC).timestamp()))
                signature = compute_signature(payload, webhook["secret"], timestamp)
                headers = {
                    "Content-Type": "application/json",
                    "X-BigRAG-Signature": signature,
                    "X-BigRAG-Timestamp": timestamp,
                    "X-BigRAG-Event": event,
                    "X-BigRAG-Delivery": str(delivery_id),
                    "User-Agent": "bigrag-webhooks/1.0",
                }
                response = await self._post_pinned(webhook["url"], payload, headers)
                last_status_code = response.status_code
                delivered = 200 <= response.status_code < 300
                if not delivered:
                    last_error = f"HTTP {response.status_code}"
            except ValueError as exc:
                last_error = f"Blocked: {exc}"
                terminal = True
            except Exception as exc:
                last_error = str(exc)

        terminal = terminal or delivered or attempt >= max_attempts
        if delivered:
            values = {
                "status": "delivered",
                "last_status_code": last_status_code,
                "last_error": None,
                "next_retry_at": None,
                "completed_at": sa.func.now(),
            }
        elif terminal:
            values = {
                "status": "failed",
                "last_status_code": last_status_code,
                "last_error": last_error,
                "next_retry_at": None,
                "completed_at": sa.func.now(),
            }
        else:
            delay = _jittered_delay(retry_delays[attempt - 1])
            logger.warning(
                "webhook delivery failed",
                webhook=webhook_id,
                webhook_event=event,
                delivery=str(delivery_id),
                attempt=attempt,
                error=last_error,
                retrying_in=round(delay, 1),
            )
            values = {
                "last_status_code": last_status_code,
                "last_error": last_error,
                "next_retry_at": datetime.now(UTC) + timedelta(seconds=int(delay)),
            }

        async with session_factory()() as session:
            await session.execute(
                sa.update(WebhookDelivery).where(WebhookDelivery.id == delivery_id).values(**values)
            )
            await session.commit()

        if delivered:
            logger.info(
                "webhook delivered",
                webhook=webhook_id,
                webhook_event=event,
                delivery=str(delivery_id),
                attempt=attempt,
                status=last_status_code,
            )
        elif terminal:
            logger.error(
                "webhook delivery permanently failed",
                webhook=webhook_id,
                webhook_event=event,
                delivery=str(delivery_id),
                error=last_error,
            )

    async def deliver_once(
        self,
        webhook: dict,
        event: str,
        payload: str,
        delivery_id: str | None = None,
    ) -> dict:
        timestamp = str(int(datetime.now(UTC).timestamp()))
        signature = compute_signature(payload, webhook["secret"], timestamp)
        headers = {
            "Content-Type": "application/json",
            "X-BigRAG-Signature": signature,
            "X-BigRAG-Timestamp": timestamp,
            "X-BigRAG-Event": event,
            "X-BigRAG-Delivery": delivery_id if delivery_id is not None else str(uuid7()),
            "User-Agent": "bigrag-webhooks/1.0",
        }
        try:
            response = await self._post_pinned(webhook["url"], payload, headers)
            return {
                "status": "delivered" if 200 <= response.status_code < 300 else "failed",
                "status_code": response.status_code,
                "error": None
                if 200 <= response.status_code < 300
                else f"HTTP {response.status_code}",
            }
        except ValueError:
            return {
                "status": "failed",
                "status_code": None,
                "error": "Blocked: URL targets a private or internal network",
            }
        except Exception as exc:
            return {
                "status": "failed",
                "status_code": None,
                "error": f"{exc.__class__.__name__}: {exc}",
            }

    async def deliver_test(self, webhook: dict, delivery_id: str | None = None) -> dict:
        secret = webhook["secret"]
        payload = orjson.dumps(
            {
                "event": "webhook.test",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ).decode()

        timestamp = str(int(datetime.now(UTC).timestamp()))
        signature = compute_signature(payload, secret, timestamp)
        headers = {
            "Content-Type": "application/json",
            "X-BigRAG-Signature": signature,
            "X-BigRAG-Timestamp": timestamp,
            "X-BigRAG-Event": "webhook.test",
            "X-BigRAG-Delivery": delivery_id if delivery_id is not None else str(uuid7()),
            "User-Agent": "bigrag-webhooks/1.0",
        }
        try:
            response = await self._post_pinned(webhook["url"], payload, headers)
            return {
                "status": "delivered" if 200 <= response.status_code < 300 else "failed",
                "status_code": response.status_code,
                "error": None
                if 200 <= response.status_code < 300
                else f"HTTP {response.status_code}",
            }
        except ValueError:
            return {
                "status": "failed",
                "status_code": None,
                "error": "Blocked: URL targets a private or internal network",
            }
        except Exception:
            return {"status": "failed", "status_code": None, "error": "Connection failed"}


webhook_dispatcher = WebhookDispatcher()
