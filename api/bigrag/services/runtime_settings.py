from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import config as config_module
from bigrag.db.models import InstanceSetting
from bigrag.models.instance_settings import (
    InstanceSettingResponse,
    InstanceSettingSpecResponse,
    InstanceSettingsResponse,
    SettingGroup,
    SettingKind,
)

SettingSource = Literal["default", "database", "bootstrap"]


@dataclass(frozen=True)
class SettingSpec:
    key: str
    group: SettingGroup
    label: str
    kind: SettingKind
    default: Any
    description: str
    options: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None
    secret: bool = False
    restart_required: bool = False


def _spec(
    key: str,
    group: SettingGroup,
    label: str,
    kind: SettingKind,
    default: Any,
    description: str,
    *,
    options: tuple[str, ...] = (),
    min: float | None = None,
    max: float | None = None,
    secret: bool = False,
    restart_required: bool = False,
) -> SettingSpec:
    return SettingSpec(
        key=key,
        group=group,
        label=label,
        kind=kind,
        default=default,
        description=description,
        options=options,
        min=min,
        max=max,
        secret=secret,
        restart_required=restart_required,
    )


SETTING_SPECS: tuple[SettingSpec, ...] = (
    _spec(
        "cors_origins",
        "security",
        "CORS origins",
        "string_list",
        [],
        "Browser origins allowed to call the API with credentials.",
    ),
    _spec(
        "trusted_proxies",
        "security",
        "Trusted proxies",
        "string_list",
        [],
        "CIDR ranges trusted for forwarded client IP headers.",
        restart_required=True,
    ),
    _spec(
        "session_cookie_secure",
        "security",
        "Secure session cookie",
        "bool",
        False,
        "Send the admin session cookie only over HTTPS.",
    ),
    _spec(
        "session_cookie_samesite",
        "security",
        "Session SameSite",
        "select",
        "lax",
        "Browser SameSite policy for admin sessions.",
        options=("lax", "strict", "none"),
    ),
    _spec(
        "session_cookie_domain",
        "security",
        "Session cookie domain",
        "string",
        None,
        "Optional cookie domain for split frontend and API deployments.",
    ),
    _spec(
        "allowed_embedding_base_urls",
        "security",
        "Allowed embedding base URLs",
        "string_list",
        [],
        "Explicit external embedding endpoints allowed by outbound URL policy.",
    ),
    _spec(
        "allow_private_embedding_base_urls",
        "security",
        "Private embedding URLs",
        "bool",
        False,
        "Allow embedding endpoints on private networks.",
    ),
    _spec(
        "allowed_chat_base_urls",
        "security",
        "Allowed chat base URLs",
        "string_list",
        [],
        "Explicit external chat endpoints allowed by outbound URL policy.",
    ),
    _spec(
        "allow_private_chat_base_urls",
        "security",
        "Private chat URLs",
        "bool",
        False,
        "Allow chat endpoints on private networks.",
    ),
    _spec(
        "allow_local_webhooks",
        "security",
        "Local webhook URLs",
        "bool",
        False,
        "Allow webhook delivery to loopback URLs.",
    ),
    _spec(
        "auth_rate_limit_window_seconds",
        "rate_limits",
        "Rate limit window",
        "int",
        60,
        "Shared auth rate-limit window in seconds.",
        min=1,
        max=3600,
    ),
    _spec(
        "auth_login_email_rate_limit",
        "rate_limits",
        "Login attempts per email",
        "int",
        5,
        "Failed login attempts allowed per email in the active window.",
        min=1,
        max=1000,
    ),
    _spec(
        "auth_login_ip_rate_limit",
        "rate_limits",
        "Login attempts per IP",
        "int",
        50,
        "Failed login attempts allowed per client IP in the active window.",
        min=1,
        max=10000,
    ),
    _spec(
        "auth_setup_ip_rate_limit",
        "rate_limits",
        "Setup attempts per IP",
        "int",
        10,
        "First-admin setup attempts allowed per client IP in the active window.",
        min=1,
        max=10000,
    ),
    _spec(
        "max_upload_size_mb",
        "ingestion",
        "Max upload size",
        "int",
        64,
        "Maximum size for a single uploaded document in MB.",
        min=1,
        max=10240,
    ),
    _spec(
        "max_batch_upload_size_mb",
        "ingestion",
        "Max batch upload size",
        "int",
        128,
        "Maximum aggregate size for a batch upload in MB.",
        min=1,
        max=102400,
    ),
    _spec(
        "max_upload_session_files",
        "ingestion",
        "Max upload session files",
        "int",
        10000,
        "Maximum files accepted by a resumable upload session.",
        min=1,
        max=1000000,
    ),
    _spec(
        "max_upload_session_size_mb",
        "ingestion",
        "Max upload session size",
        "int",
        102400,
        "Maximum aggregate size for a resumable upload session in MB.",
        min=1,
        max=1048576,
    ),
    _spec(
        "upload_session_upload_concurrency",
        "ingestion",
        "Upload session concurrency",
        "int",
        4,
        "Default browser upload concurrency for the admin UI.",
        min=1,
        max=64,
    ),
    _spec(
        "conversion_pdf_ocr_enabled",
        "ingestion",
        "PDF OCR",
        "bool",
        True,
        "OCR scanned PDFs when no embedded text is found.",
    ),
    _spec(
        "conversion_timeout",
        "ingestion",
        "Conversion timeout",
        "int",
        300,
        "Docling conversion timeout in seconds.",
        min=10,
        max=86400,
    ),
    _spec(
        "ingestion_workers",
        "ingestion",
        "Ingestion workers",
        "int",
        4,
        "Target worker concurrency for this API role.",
        min=1,
        max=256,
    ),
    _spec(
        "ingestion_batch_size",
        "ingestion",
        "Ingestion batch size",
        "int",
        128,
        "Vector insert batch size for ingestion workers.",
        min=1,
        max=4096,
    ),
    _spec(
        "queue_max_depth",
        "queue",
        "Queue max depth",
        "int",
        10000,
        "Maximum pending ingestion jobs before uploads are rejected.",
        min=1,
        max=10000000,
    ),
    _spec(
        "storage_backend",
        "storage",
        "Storage backend",
        "select",
        "local",
        "Document binary storage backend.",
        options=("local", "s3"),
        restart_required=True,
    ),
    _spec(
        "storage_s3_bucket",
        "storage",
        "S3 bucket",
        "string",
        "",
        "Bucket used when the storage backend is S3 or MinIO.",
        restart_required=True,
    ),
    _spec(
        "storage_s3_endpoint_url",
        "storage",
        "S3 endpoint URL",
        "string",
        None,
        "Optional MinIO or S3-compatible endpoint URL.",
        restart_required=True,
    ),
    _spec(
        "storage_s3_region",
        "storage",
        "S3 region",
        "string",
        "us-east-1",
        "S3 region for bucket operations.",
        restart_required=True,
    ),
    _spec(
        "storage_s3_prefix",
        "storage",
        "S3 prefix",
        "string",
        "",
        "Optional key prefix prepended to uploaded documents.",
        restart_required=True,
    ),
    _spec(
        "storage_s3_access_key_id",
        "storage",
        "S3 access key ID",
        "secret",
        None,
        "Optional static access key ID for S3-compatible storage.",
        secret=True,
        restart_required=True,
    ),
    _spec(
        "storage_s3_secret_access_key",
        "storage",
        "S3 secret access key",
        "secret",
        None,
        "Optional static secret access key for S3-compatible storage.",
        secret=True,
        restart_required=True,
    ),
    _spec(
        "storage_s3_force_path_style",
        "storage",
        "S3 path-style requests",
        "bool",
        False,
        "Use path-style bucket addressing for MinIO.",
        restart_required=True,
    ),
    _spec(
        "storage_signed_url_ttl_seconds",
        "storage",
        "Signed URL TTL",
        "int",
        900,
        "Default signed URL lifetime in seconds for future external file access.",
        min=60,
        max=604800,
    ),
    _spec(
        "backup_s3_bucket",
        "backups",
        "Backup S3 bucket",
        "string",
        "",
        "S3-compatible bucket for readable full-instance backups.",
    ),
    _spec(
        "backup_s3_endpoint_url",
        "backups",
        "Backup endpoint URL",
        "string",
        None,
        "Optional S3-compatible endpoint URL for Cloudflare R2 or MinIO.",
    ),
    _spec(
        "backup_s3_region",
        "backups",
        "Backup region",
        "string",
        "us-east-1",
        "S3 region for backup uploads.",
    ),
    _spec(
        "backup_s3_prefix",
        "backups",
        "Backup prefix",
        "string",
        "",
        "Optional prefix prepended to backup objects.",
    ),
    _spec(
        "backup_s3_access_key_id",
        "backups",
        "Backup access key ID",
        "secret",
        None,
        "Optional static access key ID for backup storage.",
        secret=True,
    ),
    _spec(
        "backup_s3_secret_access_key",
        "backups",
        "Backup secret access key",
        "secret",
        None,
        "Optional static secret access key for backup storage.",
        secret=True,
    ),
    _spec(
        "backup_s3_force_path_style",
        "backups",
        "Backup path-style requests",
        "bool",
        False,
        "Use path-style bucket addressing for backup storage.",
    ),
    _spec(
        "qdrant_search_ef",
        "search",
        "Qdrant search ef",
        "int",
        None,
        "Optional Qdrant HNSW search ef override.",
        min=1,
        max=10000,
        restart_required=True,
    ),
    _spec(
        "embedding_concurrency",
        "search",
        "Embedding concurrency",
        "int",
        8,
        "Maximum concurrent embedding requests per provider endpoint.",
        min=1,
        max=1024,
    ),
    _spec(
        "collection_cache_ttl",
        "search",
        "Collection cache TTL",
        "int",
        30,
        "Collection metadata cache TTL in seconds.",
        min=0,
        max=86400,
    ),
    _spec(
        "query_embedding_cache_ttl",
        "search",
        "Query embedding cache TTL",
        "int",
        300,
        "Query embedding cache TTL in seconds.",
        min=0,
        max=604800,
    ),
    _spec(
        "embedding_cache_mode",
        "security",
        "Embedding cache mode",
        "select",
        "encrypted",
        "Persistent chunk embedding cache behavior.",
        options=("encrypted", "disabled"),
    ),
    _spec(
        "query_result_cache_ttl",
        "search",
        "Query result cache TTL",
        "int",
        30,
        "Query result cache TTL in seconds.",
        min=0,
        max=86400,
    ),
    _spec(
        "embedding_provider",
        "search",
        "Default embedding provider",
        "select",
        "openai",
        "Fallback embedding provider for collections created without a preset.",
        options=("openai", "openai_compatible", "cohere", "voyage"),
    ),
    _spec(
        "embedding_model",
        "search",
        "Default embedding model",
        "string",
        "text-embedding-3-small",
        "Fallback embedding model for collections created without a preset.",
    ),
    _spec(
        "embedding_dimension",
        "search",
        "Default embedding dimension",
        "int",
        1536,
        "Fallback vector dimension for collections created without a preset.",
        min=1,
        max=100000,
    ),
    _spec(
        "embedding_base_url",
        "search",
        "Default embedding base URL",
        "string",
        None,
        "Optional fallback OpenAI-compatible embedding base URL.",
    ),
    _spec(
        "embedding_api_key",
        "search",
        "Default embedding API key",
        "secret",
        None,
        "Optional fallback provider key for collections created without a preset.",
        secret=True,
    ),
    _spec(
        "chat_provider",
        "chat",
        "Default chat provider",
        "select",
        "openai",
        "Default provider for new chat conversations.",
        options=("openai", "openai_compatible"),
    ),
    _spec(
        "chat_model",
        "chat",
        "Default chat model",
        "string",
        "gpt-4o-mini",
        "Default model for new chat conversations.",
    ),
    _spec(
        "chat_base_url",
        "chat",
        "Chat base URL",
        "string",
        None,
        "Optional OpenAI-compatible chat API base URL.",
    ),
    _spec(
        "chat_temperature",
        "chat",
        "Chat temperature",
        "float",
        0.2,
        "Default sampling temperature for chat completions.",
        min=0,
        max=2,
    ),
    _spec(
        "chat_max_history_messages",
        "chat",
        "Max chat history",
        "int",
        12,
        "Prior complete messages included in model context.",
        min=0,
        max=200,
    ),
    _spec(
        "chat_max_context_chars",
        "chat",
        "Max context characters",
        "int",
        120000,
        "Retrieved source characters included in model context.",
        min=1000,
        max=2000000,
    ),
    _spec(
        "webhook_delivery_timeout",
        "webhooks",
        "Delivery timeout",
        "int",
        10,
        "Webhook delivery timeout in seconds.",
        min=1,
        max=300,
    ),
    _spec(
        "webhook_retry_delays",
        "webhooks",
        "Retry delays",
        "int_list",
        [10, 30, 90],
        "Webhook retry delays in seconds.",
    ),
    _spec(
        "webhook_max_count",
        "webhooks",
        "Max webhooks",
        "int",
        50,
        "Maximum configured webhooks per instance.",
        min=0,
        max=10000,
    ),
    _spec(
        "query_log_retention_days",
        "retention",
        "Query log retention",
        "int",
        90,
        "Days to keep query logs.",
        min=1,
        max=3650,
    ),
    _spec(
        "access_log_retention_days",
        "retention",
        "Access log retention",
        "int",
        90,
        "Days to keep access logs.",
        min=1,
        max=3650,
    ),
    _spec(
        "webhook_delivery_retention_days",
        "retention",
        "Webhook delivery retention",
        "int",
        90,
        "Days to keep webhook delivery attempts.",
        min=1,
        max=3650,
    ),
    _spec(
        "progress_snapshot_retention_days",
        "retention",
        "Progress snapshot retention",
        "int",
        7,
        "Days to keep ingestion progress snapshots where durable snapshots are enabled.",
        min=1,
        max=365,
    ),
    _spec(
        "upload_session_item_retention_hours",
        "retention",
        "Upload session retention",
        "int",
        168,
        "Hours to keep upload-session item history.",
        min=1,
        max=87600,
    ),
    _spec(
        "embedding_cache_retention_days",
        "retention",
        "Embedding cache retention",
        "int",
        30,
        "Days to keep persistent embedding-cache rows after last use.",
        min=0,
        max=3650,
    ),
    _spec(
        "audit_log_retention_days",
        "retention",
        "Audit log retention",
        "int",
        365,
        "Days to keep audit events.",
        min=1,
        max=3650,
    ),
)

REGISTRY = {spec.key: spec for spec in SETTING_SPECS}
_CACHE_TTL_SECONDS = 5.0
_cached_values: dict[str, Any] | None = None
_cached_at = 0.0


def spec_responses() -> list[InstanceSettingSpecResponse]:
    return [
        InstanceSettingSpecResponse(
            key=spec.key,
            group=spec.group,
            label=spec.label,
            description=spec.description,
            kind=spec.kind,
            default=_default_for(spec),
            options=list(spec.options),
            min=spec.min,
            max=spec.max,
            secret=spec.secret,
            restart_required=spec.restart_required,
        )
        for spec in SETTING_SPECS
    ]


def invalidate_runtime_settings_cache() -> None:
    global _cached_at, _cached_values
    _cached_values = None
    _cached_at = 0.0


def sync_value(key: str) -> Any:
    if _cached_values is not None and key in _cached_values:
        return _cached_values[key]
    spec = REGISTRY[key]
    return _default_for(spec)


def _default_for(spec: SettingSpec) -> Any:
    bootstrap_settings = config_module.settings
    if hasattr(bootstrap_settings, spec.key):
        return getattr(bootstrap_settings, spec.key)
    return spec.default


def _coerce_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_parts = value.replace("\n", ",").split(",")
        return [part.strip() for part in raw_parts if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("Expected a list")


def _coerce_int_list(value: Any) -> list[int]:
    items = _coerce_list(value)
    out: list[int] = []
    for item in items:
        try:
            out.append(int(item))
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected integer values") from exc
    return out


def validate_setting_value(key: str, value: Any) -> Any:
    spec = REGISTRY.get(key)
    if spec is None:
        raise KeyError(key)
    if spec.kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        raise ValueError("Expected a boolean")
    if spec.kind == "int":
        value = _coerce_none(value)
        if value is None:
            return None if spec.default is None else spec.default
        if isinstance(value, bool):
            raise ValueError("Expected an integer")
        try:
            coerced = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected an integer") from exc
        _validate_numeric_bounds(spec, coerced)
        return coerced
    if spec.kind == "float":
        value = _coerce_none(value)
        if value is None:
            return None if spec.default is None else spec.default
        if isinstance(value, bool):
            raise ValueError("Expected a number")
        try:
            coerced = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected a number") from exc
        _validate_numeric_bounds(spec, coerced)
        return coerced
    if spec.kind == "string":
        value = _coerce_none(value)
        return None if value is None else str(value)
    if spec.kind == "secret":
        value = _coerce_none(value)
        return None if value is None else str(value)
    if spec.kind == "string_list":
        return _coerce_list(value)
    if spec.kind == "int_list":
        return _coerce_int_list(value)
    if spec.kind == "select":
        value = _coerce_none(value)
        if value is None:
            return None if spec.default is None else spec.default
        selected = str(value)
        if selected not in spec.options:
            raise ValueError(f"Expected one of: {', '.join(spec.options)}")
        return selected
    raise ValueError("Unsupported setting type")


def _validate_numeric_bounds(spec: SettingSpec, value: int | float) -> None:
    if spec.min is not None and value < spec.min:
        raise ValueError(f"Must be at least {spec.min:g}")
    if spec.max is not None and value > spec.max:
        raise ValueError(f"Must be at most {spec.max:g}")


async def get_public_settings(session: AsyncSession) -> InstanceSettingsResponse:
    rows = await _rows_by_key(session)
    values = {spec.key: _public_value(spec, rows.get(spec.key)) for spec in SETTING_SPECS}
    return InstanceSettingsResponse(specs=spec_responses(), values=values)


async def update_settings(
    session: AsyncSession,
    values: dict[str, Any],
    *,
    updated_by: UUID | None,
) -> list[str]:
    changed: list[str] = []
    rows = await _rows_by_key(session)
    for key, raw_value in values.items():
        spec = REGISTRY.get(key)
        if spec is None:
            raise KeyError(key)
        value = validate_setting_value(key, raw_value)
        row = rows.get(key)
        if row is None:
            row = InstanceSetting(key=key, updated_by=updated_by)
            session.add(row)
        if spec.secret:
            row.value = None
            row.secret_value = value
        else:
            row.value = value
            row.secret_value = None
        row.updated_by = updated_by
        changed.append(key)
    await session.commit()
    invalidate_runtime_settings_cache()
    return changed


async def reset_settings(session: AsyncSession, keys: list[str]) -> list[str]:
    target_keys = list(REGISTRY) if not keys else keys
    unknown = [key for key in target_keys if key not in REGISTRY]
    if unknown:
        raise KeyError(unknown[0])
    await session.execute(sa.delete(InstanceSetting).where(InstanceSetting.key.in_(target_keys)))
    await session.commit()
    invalidate_runtime_settings_cache()
    return target_keys


async def get_value(key: str) -> Any:
    return (await get_values([key]))[key]


async def get_values(keys: list[str]) -> dict[str, Any]:
    values = await _cached_runtime_values()
    return {key: values[key] for key in keys}


async def all_runtime_values() -> dict[str, Any]:
    return dict(await _cached_runtime_values())


async def _cached_runtime_values() -> dict[str, Any]:
    global _cached_at, _cached_values
    now = time.monotonic()
    if _cached_values is not None and now - _cached_at < _CACHE_TTL_SECONDS:
        return _cached_values
    from bigrag.db.engine import session_factory

    async with session_factory()() as session:
        rows = await _rows_by_key(session)
    values = {spec.key: _runtime_value(spec, rows.get(spec.key)) for spec in SETTING_SPECS}
    _cached_values = values
    _cached_at = now
    return values


async def _rows_by_key(session: AsyncSession) -> dict[str, InstanceSetting]:
    rows = (
        await session.scalars(sa.select(InstanceSetting).where(InstanceSetting.key.in_(REGISTRY)))
    ).all()
    return {row.key: row for row in rows}


def _runtime_value(spec: SettingSpec, row: InstanceSetting | None) -> Any:
    if row is None:
        return _default_for(spec)
    if spec.secret:
        return row.secret_value
    return row.value


def _source_for(row: InstanceSetting | None, spec: SettingSpec) -> SettingSource:
    if row is not None:
        return "database"
    if hasattr(config_module.settings, spec.key):
        return "bootstrap"
    return "default"


def _public_value(spec: SettingSpec, row: InstanceSetting | None) -> InstanceSettingResponse:
    value = None if spec.secret else _runtime_value(spec, row)
    has_value = bool(row.secret_value) if spec.secret and row is not None else row is not None
    return InstanceSettingResponse(
        key=spec.key,
        value=value,
        has_value=has_value,
        source=_source_for(row, spec),
        updated_at=row.updated_at if row is not None else None,
        updated_by=str(row.updated_by) if row is not None and row.updated_by else None,
    )
