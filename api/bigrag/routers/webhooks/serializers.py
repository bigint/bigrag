from __future__ import annotations

from bigrag.db.models import Webhook, WebhookDelivery
from bigrag.models.webhook import WebhookDeliveryResponse, WebhookResponse
from bigrag.services.webhook.events import VALID_EVENTS


def _supported_events(events: list[str]) -> list[str]:
    return [event for event in events if event in VALID_EVENTS]


def _webhook_response(wh: Webhook) -> WebhookResponse:
    return WebhookResponse(
        id=str(wh.id),
        url=wh.url,
        events=_supported_events(list(wh.events)),
        collections=list(wh.collections) if wh.collections else None,
        active=wh.active,
        created_by=str(wh.created_by) if wh.created_by else None,
        created_at=wh.created_at,
        updated_at=wh.updated_at,
    )


def _webhook_to_dict(wh: Webhook) -> dict:
    return {
        "id": wh.id,
        "url": wh.url,
        "secret": wh.secret,
        "events": _supported_events(list(wh.events)),
        "collections": list(wh.collections) if wh.collections else None,
        "active": wh.active,
        "created_by": wh.created_by,
        "created_at": wh.created_at,
        "updated_at": wh.updated_at,
    }


def _delivery_response(d: WebhookDelivery) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=str(d.id),
        webhook_id=str(d.webhook_id),
        event=d.event,
        payload=d.payload,
        status=d.status,
        attempts=d.attempts,
        last_status_code=d.last_status_code,
        last_error=d.last_error,
        created_at=d.created_at,
        completed_at=d.completed_at,
    )
