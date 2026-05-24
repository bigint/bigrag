from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import config as config_module
from bigrag.db.models import InstanceSetting
from bigrag.models.instance_settings import (
    InstanceSettingResponse,
    InstanceSettingSpecResponse,
    InstanceSettingsResponse,
)
from bigrag.services.runtime_setting_specs import SETTING_SPECS, SettingSource, SettingSpec
from bigrag.services.runtime_settings.cache import (
    _default_for,
    _public_default_for,
    _rows_by_key,
    _runtime_value,
)


def spec_responses() -> list[InstanceSettingSpecResponse]:
    return [
        InstanceSettingSpecResponse(
            key=spec.key,
            group=spec.group,
            label=spec.label,
            description=spec.description,
            kind=spec.kind,
            default=_public_default_for(spec),
            options=list(spec.options),
            min=spec.min,
            max=spec.max,
            secret=spec.secret,
        )
        for spec in SETTING_SPECS
    ]


async def get_public_settings(session: AsyncSession) -> InstanceSettingsResponse:
    rows = await _rows_by_key(session)
    values = {spec.key: _public_value(spec, rows.get(spec.key)) for spec in SETTING_SPECS}
    return InstanceSettingsResponse(specs=spec_responses(), values=values)


def _source_for(row: InstanceSetting | None, spec: SettingSpec) -> SettingSource:
    if row is not None:
        return "database"
    if hasattr(config_module.settings, spec.key):
        return "bootstrap"
    return "default"


def _public_value(spec: SettingSpec, row: InstanceSetting | None) -> InstanceSettingResponse:
    value = None if spec.secret else _runtime_value(spec, row)
    if spec.secret:
        has_value = bool(row.secret_value) if row is not None else bool(_default_for(spec))
    else:
        has_value = row is not None
    return InstanceSettingResponse(
        key=spec.key,
        value=value,
        has_value=has_value,
        source=_source_for(row, spec),
        updated_at=row.updated_at if row is not None else None,
        updated_by=str(row.updated_by) if row is not None and row.updated_by else None,
    )
