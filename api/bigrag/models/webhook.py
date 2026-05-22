from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from bigrag.services.webhook.events import VALID_EVENTS


def _validate_webhook_url(url: str) -> None:
    from bigrag.services.runtime_settings import sync_value

    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError("Webhook URL must have a hostname")
    local_http_allowed = sync_value("allow_local_webhooks") and parsed.scheme == "http"
    if parsed.scheme != "https" and not local_http_allowed:
        raise ValueError("Webhook URL must use HTTPS")


def _validate_webhook_events(events: list[str]) -> None:
    if not events:
        raise ValueError("events must not be empty")
    invalid = set(events) - VALID_EVENTS
    if invalid:
        raise ValueError(f"Invalid events: {invalid}. Valid: {sorted(VALID_EVENTS)}")


class CreateWebhookRequest(BaseModel):
    url: str
    events: list[str] = Field(min_length=1)
    collections: list[str] | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_url_and_events(self):
        _validate_webhook_url(self.url)
        _validate_webhook_events(self.events)
        return self


class UpdateWebhookRequest(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    collections: list[str] | None = None
    description: str | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        if self.url is not None:
            _validate_webhook_url(self.url)
        if self.events is not None:
            _validate_webhook_events(self.events)
        return self


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class WebhookListResponse(BaseModel):
    webhooks: list[WebhookResponse]
    total: int | None = None
    next_cursor: str | None = None


class CreateWebhookResponse(WebhookResponse):
    secret: str


class WebhookDeliveryResponse(BaseModel):
    id: str
    webhook_id: str
    event: str
    payload: dict
    status: str
    attempts: int
    last_status_code: int | None
    last_error: str | None
    created_at: datetime
    completed_at: datetime | None


class WebhookDeliveryListResponse(BaseModel):
    deliveries: list[WebhookDeliveryResponse]
    total: int | None = None
    next_cursor: str | None = None


class WebhookTestResponse(BaseModel):
    status: str
    status_code: int | None = None
    error: str | None = None
