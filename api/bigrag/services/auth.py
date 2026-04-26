"""Authentication primitives: password hashing, session tokens, and API keys.

Passwords are hashed with Argon2id. Session tokens and API keys are opaque
random strings stored as SHA-256 hashes — constant-time lookup via DB index.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()

API_KEY_PREFIX = "bigrag_sk_"
SESSION_TOKEN_BYTES = 32
API_KEY_BODY_BYTES = 32

# Computed once at import so the login route can run a verify against this
# value when the email lookup misses, masking the response-timing oracle
# that would otherwise reveal whether an email is registered. Hashed under
# the same parameters as a real password.
DUMMY_PASSWORD_HASH = _hasher.hash("bigrag-login-timing-equalizer")


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _hasher.verify(hashed, plain)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(plaintext, prefix, key_hash)``.

    Prefix is the 8-character display stub shown next to keys in the UI.
    The plaintext is only returned once — never stored.
    """
    body = secrets.token_urlsafe(API_KEY_BODY_BYTES)
    plaintext = f"{API_KEY_PREFIX}{body}"
    prefix = plaintext[: len(API_KEY_PREFIX) + 4]
    key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return plaintext, prefix, key_hash


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
