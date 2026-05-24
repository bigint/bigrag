from __future__ import annotations

import asyncio
import time
import uuid

from bigrag.logging import get_logger
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.webhook import delivery as _delivery
from bigrag.services.webhook.events import DOCUMENT_STEP_EVENTS, VALID_EVENTS
from bigrag.services.webhook.payload import (
    build_event_payload,
    build_ingestion_payload,
    matches_webhook,
)

logger = get_logger("bigrag.webhook")

_WEBHOOKS_CACHE_TTL = 5.0
_DELIVERY_CHUNK = 500
_webhooks_cache: tuple[float, list[dict]] | None = None


def invalidate_webhooks_cache() -> None:
    global _webhooks_cache
    _webhooks_cache = None


class WebhookDispatcher:
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
        webhook_event = DOCUMENT_STEP_EVENTS.get(event.step)
        if webhook_event is None:
            return

        collection = event.collection_name
        if not collection and event.document_id:
            collection = await self._get_collection_for_document(event.document_id)
        if not collection:
            return

        webhooks = await self._get_webhooks()
        payload = build_ingestion_payload(webhook_event, event, collection)
        matching_webhooks = [
            webhook for webhook in webhooks if matches_webhook(webhook, webhook_event, collection)
        ]
        await self._enqueue_deliveries(matching_webhooks, webhook_event, payload)

    async def enqueue_event(
        self,
        event: str,
        *,
        collection: str | None = None,
        data: dict | None = None,
    ) -> int:
        if event not in VALID_EVENTS:
            raise ValueError(f"Invalid webhook event: {event}")
        webhooks = await self._get_webhooks()
        matching_webhooks = [
            webhook for webhook in webhooks if matches_webhook(webhook, event, collection)
        ]
        payload = build_event_payload(event, collection, data)
        await self._enqueue_deliveries(matching_webhooks, event, payload)
        return len(matching_webhooks)

    async def enqueue_events(
        self,
        event: str,
        *,
        collection: str | None = None,
        data: list[dict] | None = None,
    ) -> int:
        if event not in VALID_EVENTS:
            raise ValueError(f"Invalid webhook event: {event}")
        items = data or []
        if not items:
            return 0
        webhooks = await self._get_webhooks()
        matching_webhooks = [
            webhook for webhook in webhooks if matches_webhook(webhook, event, collection)
        ]
        if not matching_webhooks:
            return 0
        payloads = [build_event_payload(event, collection, item) for item in items]
        await self._enqueue_deliveries_for_payloads(matching_webhooks, event, payloads)
        return len(matching_webhooks) * len(payloads)

    async def _get_webhooks(self) -> list[dict]:
        global _webhooks_cache
        now = time.monotonic()
        cached = _webhooks_cache
        if cached is not None and cached[0] > now:
            return cached[1]

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
                "active": w.active,
                "created_by": str(w.created_by) if w.created_by else None,
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat(),
            }
            for w in rows
        ]
        _webhooks_cache = (now + _WEBHOOKS_CACHE_TTL, webhooks)
        return webhooks

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

    async def _enqueue_deliveries(self, webhooks: list[dict], event: str, payload: str) -> None:
        await self._enqueue_deliveries_for_payloads(webhooks, event, [payload])

    async def _enqueue_deliveries_for_payloads(
        self, webhooks: list[dict], event: str, payloads: list[str]
    ) -> None:
        if not webhooks or not payloads:
            return
        import orjson

        from bigrag.db.engine import session_factory
        from bigrag.db.models import WebhookDelivery
        from bigrag.ids import uuid7
        from bigrag.services.jobs.actors import enqueue_webhook_outbox

        parsed_payloads = [dict(orjson.loads(payload)) for payload in payloads]

        async def _flush(rows: list[tuple]) -> None:
            if not rows:
                return
            async with session_factory()() as session:
                for delivery_id, wh_uuid, payload_data in rows:
                    session.add(
                        WebhookDelivery(
                            id=delivery_id,
                            webhook_id=wh_uuid,
                            event=event,
                            payload=dict(payload_data),
                            status="pending",
                        )
                    )
                await session.commit()
            for delivery_id, _wh_uuid, _payload_data in rows:
                enqueue_webhook_outbox(delivery_id=str(delivery_id))

        rows: list[tuple] = []
        for payload_data in parsed_payloads:
            for webhook in webhooks:
                webhook_id = webhook["id"]
                wh_uuid = uuid.UUID(webhook_id) if isinstance(webhook_id, str) else webhook_id
                rows.append((uuid7(), wh_uuid, payload_data))
                if len(rows) >= _DELIVERY_CHUNK:
                    await _flush(rows)
                    rows = []
        await _flush(rows)

    async def process_due_deliveries(
        self,
        *,
        delivery_id: uuid.UUID | None = None,
        limit: int = 25,
    ) -> int:
        return await _delivery.process_due_deliveries(delivery_id=delivery_id, limit=limit)

    async def deliver_once(
        self,
        webhook: dict,
        event: str,
        payload: str,
        delivery_id: str | None = None,
    ) -> dict:
        return await _delivery.deliver_once(webhook, event, payload, delivery_id)

    async def deliver_test(self, webhook: dict, delivery_id: str | None = None) -> dict:
        return await _delivery.deliver_test(webhook, delivery_id)


webhook_dispatcher = WebhookDispatcher()
