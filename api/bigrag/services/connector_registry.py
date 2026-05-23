from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bigrag.services.connectors.s3_sources import (
    create_s3_source,
    delete_s3_source,
    list_s3_sources,
    s3_source_public,
    s3_sync_job_public,
    trigger_s3_sync,
    update_s3_source,
)
from bigrag.services.connectors.s3_types import S3_PROVIDER, S3ConnectorError


@dataclass(frozen=True)
class ConnectorRuntime:
    slug: str
    provider: str
    display_name: str
    service_error: type[Exception]
    list_sources: Callable[..., Any]
    create_source: Callable[..., Any]
    update_source: Callable[..., Any]
    delete_source: Callable[..., Any]
    trigger_sync: Callable[..., Any]
    source_public: Callable[..., dict[str, Any]]
    sync_job_public: Callable[..., dict[str, Any]]


s3_runtime = ConnectorRuntime(
    slug="s3",
    provider=S3_PROVIDER,
    display_name="S3 / R2",
    service_error=S3ConnectorError,
    list_sources=list_s3_sources,
    create_source=create_s3_source,
    update_source=update_s3_source,
    delete_source=delete_s3_source,
    trigger_sync=trigger_s3_sync,
    source_public=s3_source_public,
    sync_job_public=s3_sync_job_public,
)

connector_runtimes = {s3_runtime.slug: s3_runtime}


def connector_runtime(slug: str) -> ConnectorRuntime | None:
    return connector_runtimes.get(slug)
