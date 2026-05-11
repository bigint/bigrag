from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from bigrag.services import crypto, redis_cache


@pytest.fixture(autouse=True)
def reset_crypto() -> None:
    crypto.configure(None)
    yield
    crypto.configure(None)


def test_redis_cache_encrypts_payloads_when_key_is_configured() -> None:
    crypto.configure(Fernet.generate_key().decode())
    value = {"embedding": [1.0, 2.0, 3.0]}

    encoded = redis_cache._encode_value(value)

    assert encoded.startswith(redis_cache.ENCRYPTED_PREFIX)
    assert b"embedding" not in encoded
    assert redis_cache._decode_value(encoded) == value


def test_redis_cache_rejects_unencrypted_payloads_when_key_is_configured() -> None:
    crypto.configure(Fernet.generate_key().decode())
    assert redis_cache._decode_value(b'{"status":"ok"}') is None


def test_redis_cache_returns_none_when_encrypted_payload_cannot_decrypt() -> None:
    crypto.configure(Fernet.generate_key().decode())
    encoded = redis_cache._encode_value({"status": "ok"})
    crypto.configure(Fernet.generate_key().decode())

    assert redis_cache._decode_value(encoded) is None
