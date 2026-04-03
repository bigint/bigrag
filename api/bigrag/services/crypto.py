"""Simple symmetric encryption for sensitive values stored in the database."""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from bigrag.config import settings

logger = logging.getLogger("bigrag.crypto")

_fernet: Fernet | None = None

# Prefix to distinguish encrypted values from plaintext (for backward compat)
_ENC_PREFIX = "enc:"


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    secret = settings.secret_key
    if not secret:
        raise RuntimeError(
            "No encryption key configured. Set BIGRAG_SECRET_KEY."
        )
    key = hashlib.pbkdf2_hmac("sha256", secret.encode(), b"bigrag-at-rest", 100_000)
    _fernet = Fernet(base64.urlsafe_b64encode(key))
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string, returning a prefixed ciphertext for storage."""
    if not plaintext:
        return plaintext
    ct = _get_fernet().encrypt(plaintext.encode()).decode()
    return f"{_ENC_PREFIX}{ct}"


def decrypt(value: str) -> str:
    """Decrypt a value. Handles both encrypted (prefixed) and legacy plaintext."""
    if not value:
        return value
    if not value.startswith(_ENC_PREFIX):
        return value  # Legacy plaintext — return as-is
    try:
        return _get_fernet().decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except InvalidToken:
        return value  # Decryption key changed — return raw (will fail at provider)
