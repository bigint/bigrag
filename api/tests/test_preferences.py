from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from rag_computer.routers import preferences
from rag_computer.services.credential_check import CredentialCheckError


def run(coro):
    return asyncio.run(coro)


def test_deep_merge_preserves_existing_nested_preferences() -> None:
    merged = preferences._deep_merge(
        {"chat": {"model": "gpt-4.1", "temperature": 0.2}, "theme": "light"},
        {"chat": {"temperature": 0.7}},
    )

    assert merged == {"chat": {"model": "gpt-4.1", "temperature": 0.7}, "theme": "light"}


def test_sensitive_preferences_are_normalized_public_and_clearable() -> None:
    incoming = preferences._normalize_sensitive({"chat": {"openai_key": " sk-live \n"}})
    merged = preferences._remove_cleared_sensitive(
        {"chat": {"openai_key": "sk-old", "model": "gpt"}, "theme": "dark"},
        {"chat": {"openai_key": ""}},
    )

    assert incoming == {"chat": {"openai_key": "sk-live"}}
    assert merged == {"chat": {"model": "gpt"}, "theme": "dark"}
    assert preferences._public_preferences({"chat": {"openai_key": "sk-live"}}) == {
        "chat": {"has_openai_key": True}
    }


def test_validate_sensitive_accepts_empty_and_rejects_invalid_values(monkeypatch) -> None:
    calls = []

    async def verify(provider, api_key, base_url):
        calls.append((provider, api_key, base_url))

    monkeypatch.setattr(preferences, "verify_provider_credentials", verify)

    run(preferences._validate_sensitive({"chat": {"openai_key": ""}}))
    run(preferences._validate_sensitive({"chat": {"openai_key": "sk-live"}}))

    assert calls == [("openai", "sk-live", None)]

    with pytest.raises(HTTPException) as non_string:
        run(preferences._validate_sensitive({"chat": {"openai_key": 123}}))
    assert non_string.value.status_code == 422
    assert non_string.value.detail == "OpenAI API key must be a string."

    async def reject(*_args):
        raise CredentialCheckError("INVALID_KEY", "bad")

    monkeypatch.setattr(preferences, "verify_provider_credentials", reject)

    with pytest.raises(HTTPException) as rejected:
        run(preferences._validate_sensitive({"chat": {"openai_key": "sk-bad"}}))
    assert rejected.value.status_code == 422
    assert "OpenAI rejected this API key" in rejected.value.detail


def test_sensitive_preferences_encrypt_decrypt_and_skip_plaintext_when_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.setattr(preferences.crypto, "is_configured", lambda: True)
    monkeypatch.setattr(preferences.crypto, "encrypt", lambda value: f"gAAAA{value}")
    monkeypatch.setattr(preferences.crypto, "decrypt", lambda value: value.removeprefix("gAAAA"))

    encrypted = preferences._encrypt_sensitive({"chat": {"openai_key": "sk-live"}})
    decrypted = preferences._decrypt_sensitive(encrypted)

    assert encrypted == {"chat": {"openai_key": "gAAAAsk-live"}}
    assert preferences._encrypt_sensitive(encrypted) == encrypted
    assert decrypted == {"chat": {"openai_key": "sk-live"}}

    monkeypatch.setattr(preferences.crypto, "is_configured", lambda: False)

    assert preferences._encrypt_sensitive({"chat": {"openai_key": "sk-live"}}) == {
        "chat": {"openai_key": "sk-live"}
    }
    assert preferences._decrypt_sensitive(encrypted) == encrypted


def test_decrypt_preferences_handles_non_dict_values() -> None:
    assert preferences.decrypt_preferences([]) == {}
