from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


def compute_signature(payload: str, secret: str, timestamp: str) -> str:
    signed_payload = f"{timestamp}.{payload}"
    digest = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(
    payload: str,
    secret: str,
    received: str,
    timestamp: str,
) -> bool:
    expected = compute_signature(payload, secret, timestamp)
    return hmac.compare_digest(expected, received)
