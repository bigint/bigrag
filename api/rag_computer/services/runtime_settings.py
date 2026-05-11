from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from rag_computer import config as config_module
from rag_computer.db.models import InstanceSetting
from rag_computer.models.instance_settings import (
    InstanceSettingResponse,
    InstanceSettingSpecResponse,
    InstanceSettingsResponse,
)
from rag_computer.services.runtime_setting_specs import (
    REGISTRY,
    SETTING_SPECS,
    SettingSource,
    SettingSpec,
)

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
    from rag_computer.db.engine import session_factory

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
