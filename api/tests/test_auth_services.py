from __future__ import annotations

from cryptography.fernet import Fernet

from bigrag.services import auth


def test_api_key_hash_lookup_checks_current_previous_and_legacy(
    monkeypatch,
) -> None:
    current = Fernet.generate_key().decode()
    previous = Fernet.generate_key().decode()
    token = "bigrag_sk_test_secret"

    monkeypatch.setattr(auth._config_settings, "master_key", current)
    monkeypatch.setattr(auth._config_settings, "master_key_previous", [previous])

    hashes = auth.api_key_hashes_for_lookup(token)

    assert hashes[0] == auth.hash_api_key(token)
    assert len(hashes) == 3
    assert len(set(hashes)) == 3


def test_api_key_hash_lookup_keeps_legacy_without_master_key(
    monkeypatch,
) -> None:
    token = "bigrag_sk_test_secret"

    monkeypatch.setattr(auth._config_settings, "master_key", None)
    monkeypatch.setattr(auth._config_settings, "master_key_previous", [])

    assert auth.api_key_hashes_for_lookup(token) == [auth.hash_api_key(token)]
