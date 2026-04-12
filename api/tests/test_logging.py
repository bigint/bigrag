"""Unit tests for the secret-redaction structlog processor."""

from __future__ import annotations

import pytest

from bigrag.logging import _SENSITIVE_KEYS, redact_secrets


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "embedding_api_key",
        "rerank_api_key",
        "s3_access_key",
        "s3_secret_key",
        "password",
        "password_hash",
        "session_token",
        "token",
        "authorization",
        "cookie",
    ],
)
def test_top_level_sensitive_keys_are_redacted(key):
    event = {"event": "anything", key: "super-secret-value", "safe": "ok"}
    out = redact_secrets(None, "info", event)
    assert out[key] == "[REDACTED]"
    assert out["safe"] == "ok"


def test_case_insensitive_matching():
    event = {"Authorization": "Bearer xyz", "API_KEY": "sk-abc"}
    out = redact_secrets(None, "info", event)
    assert out["Authorization"] == "[REDACTED]"
    assert out["API_KEY"] == "[REDACTED]"


def test_nested_dict_is_redacted():
    event = {
        "event": "config",
        "collection": {
            "name": "docs",
            "embedding_api_key": "sk-abc",
            "model": "text-3-small",
            "rerank": {"rerank_api_key": "co-abc", "model": "rerank-v3.5"},
        },
    }
    out = redact_secrets(None, "info", event)
    assert out["collection"]["embedding_api_key"] == "[REDACTED]"
    assert out["collection"]["model"] == "text-3-small"
    assert out["collection"]["rerank"]["rerank_api_key"] == "[REDACTED]"
    assert out["collection"]["rerank"]["model"] == "rerank-v3.5"


def test_list_of_dicts_is_redacted():
    event = {"keys": [{"api_key": "a"}, {"api_key": "b", "name": "prod"}]}
    out = redact_secrets(None, "info", event)
    assert out["keys"][0]["api_key"] == "[REDACTED]"
    assert out["keys"][1]["api_key"] == "[REDACTED]"
    assert out["keys"][1]["name"] == "prod"


def test_non_sensitive_values_pass_through_unchanged():
    event = {"event": "hi", "n": 42, "nested": {"x": [1, 2, 3]}, "t": True}
    out = redact_secrets(None, "info", event)
    assert out == event


def test_sensitive_keys_set_includes_common_variants():
    # Guard against accidental removal during future refactors.
    for must_have in [
        "api_key",
        "password",
        "authorization",
        "s3_secret_key",
        "session_token",
    ]:
        assert must_have in _SENSITIVE_KEYS
