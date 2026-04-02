from __future__ import annotations

import pytest
from bigrag.models.webhook import (
    CreateWebhookRequest,
    UpdateWebhookRequest,
    VALID_EVENTS,
)


def test_valid_create_request():
    req = CreateWebhookRequest(
        url="https://example.com/webhook",
        events=["document.ready", "document.failed"],
        description="test hook",
    )
    assert req.url == "https://example.com/webhook"
    assert req.events == ["document.ready", "document.failed"]
    assert req.collections is None


def test_create_request_with_collections():
    req = CreateWebhookRequest(
        url="https://example.com/webhook",
        events=["document.ready"],
        collections=["docs", "reports"],
    )
    assert req.collections == ["docs", "reports"]


def test_create_request_rejects_http_non_localhost():
    with pytest.raises(ValueError, match="HTTPS"):
        CreateWebhookRequest(
            url="http://remote-server.com/webhook",
            events=["document.ready"],
        )


def test_create_request_allows_http_localhost():
    req = CreateWebhookRequest(
        url="http://localhost:3000/webhook",
        events=["document.ready"],
    )
    assert req.url == "http://localhost:3000/webhook"


def test_create_request_allows_http_127():
    req = CreateWebhookRequest(
        url="http://127.0.0.1:3000/webhook",
        events=["document.ready"],
    )
    assert req.url == "http://127.0.0.1:3000/webhook"


def test_create_request_rejects_empty_events():
    with pytest.raises(ValueError):
        CreateWebhookRequest(
            url="https://example.com/webhook",
            events=[],
        )


def test_create_request_rejects_invalid_event():
    with pytest.raises(ValueError, match="Invalid events"):
        CreateWebhookRequest(
            url="https://example.com/webhook",
            events=["document.ready", "invalid.event"],
        )


def test_update_request_partial():
    req = UpdateWebhookRequest(active=False)
    assert req.active is False
    assert req.url is None
    assert req.events is None


def test_update_request_validates_events():
    with pytest.raises(ValueError, match="Invalid events"):
        UpdateWebhookRequest(events=["bad.event"])


def test_valid_events_constant():
    assert "document.ready" in VALID_EVENTS
    assert "document.failed" in VALID_EVENTS
    assert "document.processing" in VALID_EVENTS
