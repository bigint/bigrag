from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from typing import Any

import orjson

from bigrag import __version__

from .constants import BACKUP_FORMAT_VERSION
from .target import BackupUploadStats, S3BackupTarget


def _signing_key() -> bytes | None:
    try:
        from bigrag.config import settings as _settings
    except Exception:
        return None
    key = getattr(_settings, "master_key", None)
    if not key:
        return None
    return key.encode("utf-8") if isinstance(key, str) else key


def _manifest(
    *,
    job_id: uuid.UUID,
    target: S3BackupTarget,
    backup_prefix: str,
    table_counts: dict[str, int],
    vector_counts: dict[str, int],
    stats: BackupUploadStats,
    db_revision: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "backup_id": str(job_id),
        "format_version": BACKUP_FORMAT_VERSION,
        "app_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "encryption": "redacted",
        "redaction": {
            "secret_columns": True,
            "embedding_cache_vectors": True,
            "vector_store_vectors": True,
            "staged_uploads": False,
        },
        "destination": {
            "bucket": target.bucket,
            "endpoint_url": target.endpoint_url,
            "region": target.region,
            "prefix": backup_prefix,
        },
        "tables": table_counts,
        "vector_store": {"provider": "per_collection"},
        "vectors": vector_counts,
        "object_count": stats.object_count,
        "byte_count": stats.bytes,
        "db_revision": db_revision,
    }
    key = _signing_key()
    if key is not None:
        body = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
        payload["hmac_sha256"] = hmac.new(key, body, hashlib.sha256).hexdigest()
    return payload
