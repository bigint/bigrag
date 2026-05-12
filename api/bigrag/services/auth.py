from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from bigrag.config import settings as _config_settings

_hasher = PasswordHasher()

API_KEY_PREFIX = "bigrag_sk_"
SESSION_TOKEN_BYTES = 32
API_KEY_BODY_BYTES = 32

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


def _api_key_pepper() -> bytes | None:
    from bigrag import config as _config_module

    master_key = getattr(_config_module.settings, "master_key", None) or _config_settings.master_key
    if not master_key:
        return None
    return master_key.encode("utf-8")


def generate_api_key() -> tuple[str, str, str]:

    body = secrets.token_urlsafe(API_KEY_BODY_BYTES)
    plaintext = f"{API_KEY_PREFIX}{body}"
    prefix = plaintext[: len(API_KEY_PREFIX) + 4]
    key_hash = hash_api_key(plaintext)
    return plaintext, prefix, key_hash


def hash_api_key(plaintext: str) -> str:
    pepper = _api_key_pepper()
    if pepper is None:
        return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return hmac.new(pepper, plaintext.encode("utf-8"), hashlib.sha256).hexdigest()
