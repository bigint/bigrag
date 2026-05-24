from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import InstanceSetting
from bigrag.services.runtime_setting_specs import REGISTRY, SETTING_SPECS, SettingSpec
from bigrag.services.runtime_settings.cache import (
    _default_for,
    _rows_by_key,
    _runtime_value,
    set_runtime_settings_cache,
)
from bigrag.services.runtime_settings.validate import validate_setting_value


async def update_settings(
    session: AsyncSession,
    values: dict[str, Any],
    *,
    updated_by: UUID | None,
    values_are_validated: bool = False,
) -> list[str]:
    changed: list[str] = []
    rows = await _rows_by_key(session)
    for key, raw_value in values.items():
        spec = REGISTRY.get(key)
        if spec is None:
            raise KeyError(key)
        value = raw_value if values_are_validated else validate_setting_value(key, raw_value)
        row = rows.get(key)
        if _stored_value_matches(spec, row, value):
            continue
        if row is None:
            row = InstanceSetting(key=key, updated_by=updated_by)
            session.add(row)
            rows[key] = row
        if spec.secret:
            row.value = None
            row.secret_value = value
        else:
            row.value = value
            row.secret_value = None
        row.updated_by = updated_by
        changed.append(key)
    if not changed:
        return changed
    await session.commit()
    set_runtime_settings_cache(
        {spec.key: _runtime_value(spec, rows.get(spec.key)) for spec in SETTING_SPECS}
    )
    return changed


async def changed_setting_values(session: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    rows = await _rows_by_key(session)
    changed: dict[str, Any] = {}
    for key, raw_value in values.items():
        spec = REGISTRY.get(key)
        if spec is None:
            raise KeyError(key)
        value = validate_setting_value(key, raw_value)
        if not _stored_value_matches(spec, rows.get(key), value):
            changed[key] = value
    return changed


async def reset_settings(session: AsyncSession, keys: list[str]) -> list[str]:
    target_keys = list(REGISTRY) if not keys else keys
    unknown = [key for key in target_keys if key not in REGISTRY]
    if unknown:
        raise KeyError(unknown[0])
    rows = await _rows_by_key(session)
    await session.execute(sa.delete(InstanceSetting).where(InstanceSetting.key.in_(target_keys)))
    await session.commit()
    for key in target_keys:
        rows.pop(key, None)
    set_runtime_settings_cache(
        {spec.key: _runtime_value(spec, rows.get(spec.key)) for spec in SETTING_SPECS}
    )
    return target_keys


def _stored_value_matches(spec: SettingSpec, row: InstanceSetting | None, value: Any) -> bool:
    if row is None:
        return value == _default_for(spec)
    if spec.secret:
        return row.secret_value == value
    return row.value == value
