from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

_fernet: Fernet | None = None
_FERNET_PREFIX = "gAAAA"

logger = logging.getLogger("bigrag.crypto")


class CryptoNotConfiguredError(RuntimeError):
    pass


def configure(master_key: str | None) -> None:

    global _fernet
    if not master_key:
        _fernet = None
        return
    key_bytes = master_key.encode() if isinstance(master_key, str) else master_key
    try:
        _fernet = Fernet(key_bytes)
    except Exception as exc:
        raise ValueError(
            "BIGRAG_MASTER_KEY is not a valid Fernet key (expected 32-byte urlsafe-base64)."
        ) from exc


def is_configured() -> bool:
    return _fernet is not None


def _require() -> Fernet:
    if _fernet is None:
        raise CryptoNotConfiguredError(
            "BIGRAG_MASTER_KEY is not set. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and export it."
        )
    return _fernet


def encrypt(plaintext: str) -> str:
    return _require().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _require().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Encrypted column failed to decrypt — wrong BIGRAG_MASTER_KEY?") from exc


class EncryptedString(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if not value.startswith(_FERNET_PREFIX):
            logger.warning(
                "crypto: read a plaintext value in an encrypted column — "
                "it will be encrypted on the next write"
            )
            return value
        return decrypt(value)
