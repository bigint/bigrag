from __future__ import annotations

import hashlib
import hmac
import json

from bigrag.services.webhook import (
    _matches_webhook,
    compute_signature,
)


def test_compute_signature():
    secret = "whsec_test123"
    payload = json.dumps({"event": "document.ready", "document_id": "abc"})
    sig = compute_signature(payload, secret)
    assert sig.startswith("sha256=")
    digest = sig[len("sha256=") :]
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert digest == expected


def test_compute_signature_deterministic():
    secret = "whsec_test"
    payload = '{"key":"value"}'
    sig1 = compute_signature(payload, secret)
    sig2 = compute_signature(payload, secret)
    assert sig1 == sig2


def test_matches_webhook_event_match():
    webhook = {
        "events": ["document.ready", "document.failed"],
        "collections": None,
        "active": True,
    }
    assert _matches_webhook(webhook, "document.ready", "docs") is True
    assert _matches_webhook(webhook, "document.processing", "docs") is False


def test_matches_webhook_collection_filter():
    webhook = {
        "events": ["document.ready"],
        "collections": ["docs", "reports"],
        "active": True,
    }
    assert _matches_webhook(webhook, "document.ready", "docs") is True
    assert _matches_webhook(webhook, "document.ready", "other") is False


def test_matches_webhook_null_collections_matches_all():
    webhook = {
        "events": ["document.ready"],
        "collections": None,
        "active": True,
    }
    assert _matches_webhook(webhook, "document.ready", "any_collection") is True


def test_matches_webhook_inactive():
    webhook = {
        "events": ["document.ready"],
        "collections": None,
        "active": False,
    }
    assert _matches_webhook(webhook, "document.ready", "docs") is False
