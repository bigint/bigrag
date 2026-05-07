from __future__ import annotations

import asyncio

import pytest
from cryptography.fernet import Fernet

from bigrag.services import crypto, embedding_cache


@pytest.fixture(autouse=True)
def reset_crypto() -> None:
    crypto.configure(None)
    yield
    crypto.configure(None)


def test_embedding_cache_encrypts_vectors_when_key_is_configured() -> None:
    crypto.configure(Fernet.generate_key().decode())
    vector = [0.1, -0.2, 3.5]

    blob = embedding_cache._encode_vector(vector)
    decoded, legacy = embedding_cache._decode_vector(blob, 3)

    assert blob.startswith(b"gAAAA")
    assert blob != embedding_cache._pack(vector)
    assert decoded == pytest.approx(vector)
    assert legacy is False


def test_embedding_cache_decodes_legacy_plaintext_vectors() -> None:
    vector = [0.1, -0.2, 3.5]

    decoded, legacy = embedding_cache._decode_vector(embedding_cache._pack(vector), 3)

    assert decoded == pytest.approx(vector)
    assert legacy is True


def test_embedding_cache_skips_corrupt_ciphertext() -> None:
    crypto.configure(Fernet.generate_key().decode())

    decoded, legacy = embedding_cache._decode_vector(b"gAAAAbad", 3)

    assert decoded is None
    assert legacy is False


def test_embedding_cache_disabled_mode_turns_cache_off(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "disabled"}

    crypto.configure(Fernet.generate_key().decode())
    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)

    assert asyncio.run(embedding_cache._cache_enabled()) is False


def test_embedding_cache_without_key_turns_cache_off(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "encrypted"}

    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)

    assert asyncio.run(embedding_cache._cache_enabled()) is False
