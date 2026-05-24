from __future__ import annotations

import asyncio
import time
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import config as config_module
from bigrag.db.models import InstanceSetting
from bigrag.services.runtime_setting_specs import REGISTRY, SETTING_SPECS, SettingSpec

_CACHE_TTL_SECONDS = 5.0
_cached_values: dict[str, Any] | None = None
_cached_at = 0.0
_cache_refresh_lock = asyncio.Lock()


def set_runtime_settings_cache(values: dict[str, Any]) -> None:
    global _cached_at, _cached_values
    _cached_values = dict(values)
    _cached_at = time.monotonic()


def sync_value(key: str) -> Any:
    if _cached_values is not None and key in _cached_values:
        return _cached_values[key]
    spec = REGISTRY[key]
    return _default_for(spec)


def default_values(keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        spec = REGISTRY.get(key)
        if spec is None:
            raise KeyError(key)
        out[key] = _default_for(spec)
    return out


def _default_for(spec: SettingSpec) -> Any:
    bootstrap_settings = config_module.settings
    if hasattr(bootstrap_settings, spec.key):
        return getattr(bootstrap_settings, spec.key)
    return spec.default


def _public_default_for(spec: SettingSpec) -> Any:
    if spec.secret:
        return None
    return _default_for(spec)


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
    async with _cache_refresh_lock:
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
