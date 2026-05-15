from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from bigrag import __version__

from .constants import BACKUP_FORMAT_VERSION
from .target import BackupUploadStats, S3BackupTarget


def _manifest(
    *,
    job_id: uuid.UUID,
    target: S3BackupTarget,
    backup_prefix: str,
    table_counts: dict[str, int],
    vector_counts: dict[str, int],
    upload_count: int,
    stats: BackupUploadStats,
) -> dict[str, Any]:
    return {
        "backup_id": str(job_id),
        "format_version": BACKUP_FORMAT_VERSION,
        "app_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "encryption": "redacted",
        "redaction": {
            "secret_columns": True,
            "embedding_cache_vectors": True,
            "vector_store_vectors": True,
            "raw_uploads": False,
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
        "uploads": {"files": upload_count},
        "object_count": stats.object_count,
        "byte_count": stats.bytes,
    }
