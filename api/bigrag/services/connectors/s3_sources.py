from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.s3_client import probe_s3_credentials, source_credential
from bigrag.services.connectors.s3_types import (
    S3_DEFAULT_REGION,
    S3_PROVIDER,
    S3ConnectorError,
    clean_s3_prefix,
    normalize_s3_region,
    s3_metadata,
    s3_root_id,
    s3_root_name,
    s3_source_config_public,
    source_s3_config,
)
from bigrag.services.connectors.sources import (
    create_source,
    delete_source,
    list_sources,
    source_public,
    sync_job_public,
    trigger_sync,
    update_source,
)

S3_QUEUED_MESSAGE = "S3 sync queued"


async def list_s3_sources(
    session,
    *,
    collection_name: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    return await list_sources(
        session,
        provider=S3_PROVIDER,
        collection_name=collection_name,
        shape_config=s3_source_config_public,
    )


async def create_s3_source(
    session,
    *,
    user_id: str,
    collection_name: str,
    bucket: str,
    prefix: str,
    region: str | None,
    endpoint_url: str | None,
    force_path_style: bool,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None,
    schedule_enabled: bool,
    sync_interval_hours: int,
    metadata: dict,
) -> tuple[ConnectorSource, ConnectorSyncJob]:
    values = _source_values(
        bucket=bucket,
        prefix=prefix,
        region=region,
        endpoint_url=endpoint_url,
        force_path_style=force_path_style,
        metadata=metadata,
    )
    await probe_s3_credentials(
        bucket=values["bucket"],
        prefix=values["prefix"],
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
        region=values["region"],
        endpoint_url=values["endpoint_url"],
        force_path_style=values["force_path_style"],
    )
    return await create_source(
        session,
        provider=S3_PROVIDER,
        collection_name=collection_name,
        root_id=values["root_id"],
        root_name=values["root_name"],
        metadata=values["metadata"],
        user_id=user_id,
        schedule_enabled=schedule_enabled,
        sync_interval_hours=sync_interval_hours,
        start_sync_job=start_s3_sync_job,
        queued_message=S3_QUEUED_MESSAGE,
        credential_values={
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
            "session_token": session_token,
            "session_token_set": True,
            "region": values["region"],
            "endpoint_url": values["endpoint_url"],
            "force_path_style": values["force_path_style"],
        },
    )


async def update_s3_source(
    session,
    *,
    source_id: str,
    bucket: str | None,
    prefix: str | None,
    region: str | None,
    endpoint_url: str | None,
    endpoint_url_set: bool,
    force_path_style: bool | None,
    access_key_id: str | None,
    secret_access_key: str | None,
    session_token: str | None,
    session_token_set: bool,
    schedule_enabled: bool | None,
    sync_interval_hours: int | None,
    metadata: dict | None,
) -> ConnectorSource:
    source = await source_by_id_for_s3(session, source_id=source_id)
    current = source_s3_config(source)
    next_bucket = bucket.strip() if bucket is not None else current["bucket"]
    next_prefix = clean_s3_prefix(prefix) if prefix is not None else current["prefix"]
    next_endpoint = _clean_optional(endpoint_url) if endpoint_url_set else current["endpoint_url"]
    next_region = normalize_s3_region(
        region or current["region"] or S3_DEFAULT_REGION, next_endpoint
    )
    next_force_path_style = (
        force_path_style if force_path_style is not None else current["force_path_style"]
    )
    existing = await source_credential(session, source)
    rotating_keys = access_key_id is not None or secret_access_key is not None
    if bool(access_key_id) != bool(secret_access_key):
        raise S3ConnectorError("S3 access key ID and secret access key must be rotated together")
    next_access_key_id = access_key_id.strip() if access_key_id else existing.access_key_id
    next_secret_access_key = (
        secret_access_key.strip() if secret_access_key else existing.secret_access_key
    )
    if session_token_set:
        next_session_token = _clean_optional(session_token)
    elif rotating_keys:
        next_session_token = None
    else:
        next_session_token = existing.session_token
    await probe_s3_credentials(
        bucket=next_bucket,
        prefix=next_prefix,
        access_key_id=next_access_key_id,
        secret_access_key=next_secret_access_key,
        session_token=next_session_token,
        region=next_region,
        endpoint_url=next_endpoint,
        force_path_style=next_force_path_style,
    )
    user_metadata = (
        metadata if metadata is not None else dict((source.meta or {}).get("user_metadata") or {})
    )
    values = _source_values(
        bucket=next_bucket,
        prefix=next_prefix,
        region=next_region,
        endpoint_url=next_endpoint,
        force_path_style=next_force_path_style,
        metadata=user_metadata,
    )
    return await update_source(
        session,
        provider=S3_PROVIDER,
        source_id=source_id,
        not_found_message="S3 source not found",
        schedule_enabled=schedule_enabled,
        sync_interval_hours=sync_interval_hours,
        root_id=values["root_id"],
        root_name=values["root_name"],
        metadata=values["metadata"],
        credential_values={
            "access_key_id": access_key_id.strip() if access_key_id else None,
            "secret_access_key": secret_access_key.strip() if secret_access_key else None,
            "session_token": next_session_token,
            "session_token_set": session_token_set or rotating_keys,
            "region": next_region,
            "endpoint_url": next_endpoint,
            "force_path_style": next_force_path_style,
        },
    )


async def trigger_s3_sync(
    session,
    *,
    user_id: str,
    source_id: str,
    trigger: str = "manual",
) -> ConnectorSyncJob:
    return await trigger_sync(
        session,
        provider=S3_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        trigger=trigger,
        not_found_message="S3 source not found",
        start_sync_job=start_s3_sync_job,
        queued_message=S3_QUEUED_MESSAGE,
    )


async def delete_s3_source(session, *, source_id: str) -> None:
    await delete_source(
        session,
        provider=S3_PROVIDER,
        source_id=source_id,
        not_found_message="S3 source not found",
    )


async def source_by_id_for_s3(session, *, source_id: str) -> ConnectorSource:
    from bigrag.services.connectors.sources import source_by_id

    return await source_by_id(
        session,
        provider=S3_PROVIDER,
        source_id=source_id,
        not_found_message="S3 source not found",
    )


def s3_source_public(source: ConnectorSource) -> dict[str, Any]:
    return source_public(S3_PROVIDER, source, shape_config=s3_source_config_public)


def s3_sync_job_public(job: ConnectorSyncJob) -> dict[str, Any]:
    return sync_job_public(S3_PROVIDER, job)


def start_s3_sync_job(job_id: str) -> None:
    from bigrag.services.jobs.actors import enqueue_s3_sync

    enqueue_s3_sync(job_id)


def _source_values(
    *,
    bucket: str,
    prefix: str | None,
    region: str | None,
    endpoint_url: str | None,
    force_path_style: bool,
    metadata: dict,
) -> dict[str, Any]:
    clean_bucket = bucket.strip()
    clean_prefix = clean_s3_prefix(prefix)
    clean_endpoint = _clean_optional(endpoint_url)
    clean_region = normalize_s3_region(region, clean_endpoint)
    if not clean_bucket:
        raise S3ConnectorError("S3 bucket is required")
    if not clean_region:
        raise S3ConnectorError("S3 region is required")
    return {
        "bucket": clean_bucket,
        "prefix": clean_prefix,
        "region": clean_region,
        "endpoint_url": clean_endpoint,
        "force_path_style": force_path_style,
        "root_id": s3_root_id(clean_bucket, clean_prefix),
        "root_name": s3_root_name(clean_bucket, clean_prefix),
        "metadata": s3_metadata(
            bucket=clean_bucket,
            prefix=clean_prefix,
            region=clean_region,
            endpoint_url=clean_endpoint,
            force_path_style=force_path_style,
            user_metadata=metadata,
        ),
    }


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None
