from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

_fernet: Fernet | None = None
_previous_fernets: list[Fernet] = []
_FERNET_PREFIX = "gAAAA"
_FERNET_BYTES_PREFIX = b"gAAAA"

logger = logging.getLogger("rag_computer.crypto")


class CryptoNotConfiguredError(RuntimeError):
    pass


def _build_fernet(master_key: str | bytes, *, label: str) -> Fernet:
    key_bytes = master_key.encode() if isinstance(master_key, str) else master_key
    try:
        return Fernet(key_bytes)
    except Exception as exc:
        raise ValueError(
            f"{label} is not a valid Fernet key (expected 32-byte urlsafe-base64)."
        ) from exc


def configure(master_key: str | None, previous_keys: list[str] | None = None) -> None:
    global _fernet, _previous_fernets
    _previous_fernets = []
    if not master_key:
        _fernet = None
        return
    _fernet = _build_fernet(master_key, label="RAG_COMPUTER_MASTER_KEY")
    for raw in previous_keys or []:
        if raw:
            _previous_fernets.append(_build_fernet(raw, label="RAG_COMPUTER_MASTER_KEY_PREVIOUS"))


def is_configured() -> bool:
    return _fernet is not None


def _require() -> Fernet:
    if _fernet is None:
        raise CryptoNotConfiguredError(
            "RAG_COMPUTER_MASTER_KEY is not set. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and export it."
        )
    return _fernet


def encrypt(plaintext: str) -> str:
    return _require().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    raw = ciphertext.encode()
    primary = _require()
    try:
        return primary.decrypt(raw).decode()
    except InvalidToken:
        for prev in _previous_fernets:
            try:
                return prev.decrypt(raw).decode()
            except InvalidToken:
                continue
        raise ValueError(
            "Encrypted column failed to decrypt — wrong RAG_COMPUTER_MASTER_KEY "
            "(set RAG_COMPUTER_MASTER_KEY_PREVIOUS to read values written under the old key)."
        ) from None


def encrypt_bytes(plaintext: bytes) -> bytes:
    return _require().encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    primary = _require()
    try:
        return primary.decrypt(ciphertext)
    except InvalidToken:
        for prev in _previous_fernets:
            try:
                return prev.decrypt(ciphertext)
            except InvalidToken:
                continue
        raise ValueError(
            "Encrypted value failed to decrypt — wrong RAG_COMPUTER_MASTER_KEY "
            "(set RAG_COMPUTER_MASTER_KEY_PREVIOUS to read values written under the old key)."
        ) from None


def looks_encrypted_bytes(value: bytes) -> bool:
    return value.startswith(_FERNET_BYTES_PREFIX)


class EncryptedString(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, _dialect):  # type: ignore[override]
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, _dialect):  # type: ignore[override]
        if value is None:
            return None
        if not value.startswith(_FERNET_PREFIX):
            logger.warning(
                "crypto: read a plaintext value in an encrypted column — "
                "it will be encrypted on the next write"
            )
            return value
        return decrypt(value)
