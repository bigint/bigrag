from __future__ import annotations

BACKUP_FORMAT_VERSION = 1
BACKUP_ROOT = "backups"
REDACTED = "[REDACTED]"
_SENSITIVE_COLUMN_NAMES = frozenset(
    {
        "access_token",
        "api_key",
        "client_secret",
        "embedding_api_key",
        "key_hash",
        "password_hash",
        "qdrant_api_key",
        "refresh_token",
        "reranking_api_key",
        "secret",
        "secret_value",
        "session_token",
        "token_hash",
        "vector",
    }
)
