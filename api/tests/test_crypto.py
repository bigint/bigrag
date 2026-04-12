"""Unit tests for the Fernet wrapper and EncryptedString TypeDecorator."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from bigrag.services import crypto
from bigrag.services.crypto import CryptoNotConfiguredError, EncryptedString


@pytest.fixture(autouse=True)
def _reset_crypto():
    crypto.configure(None)
    yield
    crypto.configure(None)


def test_requires_configure_before_use():
    with pytest.raises(CryptoNotConfiguredError):
        crypto.encrypt("hello")


def test_roundtrip():
    crypto.configure(Fernet.generate_key().decode())
    cipher = crypto.encrypt("sk-live-super-secret")
    assert cipher.startswith("gAAAA")
    assert crypto.decrypt(cipher) == "sk-live-super-secret"


def test_invalid_key_rejected():
    with pytest.raises(ValueError, match="valid Fernet key"):
        crypto.configure("not-a-valid-fernet-key")


def test_wrong_key_on_decrypt_raises():
    crypto.configure(Fernet.generate_key().decode())
    cipher = crypto.encrypt("payload")
    crypto.configure(Fernet.generate_key().decode())
    with pytest.raises(ValueError, match="failed to decrypt"):
        crypto.decrypt(cipher)


def test_encrypted_string_binds_and_restores():
    crypto.configure(Fernet.generate_key().decode())
    t = EncryptedString()
    bound = t.process_bind_param("hello", None)
    assert bound != "hello"
    assert bound.startswith("gAAAA")
    assert t.process_result_value(bound, None) == "hello"


def test_encrypted_string_passes_through_none():
    crypto.configure(Fernet.generate_key().decode())
    t = EncryptedString()
    assert t.process_bind_param(None, None) is None
    assert t.process_result_value(None, None) is None
