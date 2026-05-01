from __future__ import annotations

import asyncio
import ipaddress
import socket
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

VALID_EVENTS = frozenset({"document.ready", "document.failed", "document.processing"})

MAX_WEBHOOKS = 50


def _is_blocked_ip(ip_str: str) -> bool:

    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if addr.is_loopback:
        return False
    return addr.is_private or addr.is_reserved or addr.is_link_local or addr.is_multicast


async def resolve_and_validate_url(url: str) -> None:

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Webhook URL must have a hostname")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addrinfo = await asyncio.to_thread(socket.getaddrinfo, hostname, port)
    except socket.gaierror as exc:
        raise ValueError("Cannot resolve webhook URL hostname") from exc
    for _, _, _, _, sockaddr in addrinfo:
        if _is_blocked_ip(sockaddr[0]):
            raise ValueError("Webhook URL must not target private or internal networks")


def _validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError("Webhook URL must have a hostname")
    is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_localhost):
        raise ValueError("Webhook URL must use HTTPS (HTTP allowed only for localhost)")


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
    total: int


class WebhookTestResponse(BaseModel):
    status: str
    status_code: int | None = None
    error: str | None = None
