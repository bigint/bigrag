
from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class Webhook(TypedDict):
    id: str
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool
    created_by: str | None
    created_at: str
    updated_at: str


class CreateWebhookBody(TypedDict):
    url: str
    events: list[str]
    collections: NotRequired[list[str]]
    description: NotRequired[str]


class CreateWebhookResponse(TypedDict):
    id: str
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool
    created_by: str | None
    created_at: str
    updated_at: str
    secret: str


class UpdateWebhookBody(TypedDict, total=False):
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool


class WebhookListResponse(TypedDict):
    webhooks: list[Webhook]
    total: int


class WebhookDelivery(TypedDict):
    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_status_code: int | None
    last_error: str | None
    created_at: str
    completed_at: str | None


class WebhookDeliveryListResponse(TypedDict):
    deliveries: list[WebhookDelivery]
    total: int


class WebhookTestResponse(TypedDict):
    status: str
    status_code: int | None
    error: str | None
