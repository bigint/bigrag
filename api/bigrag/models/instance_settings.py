from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SettingKind = Literal[
    "bool", "int", "float", "string", "string_list", "int_list", "select", "secret"
]
SettingGroup = Literal[
    "security",
    "ingestion",
    "storage",
    "vector_store",
    "queue",
    "search",
    "chat",
    "webhooks",
    "rate_limits",
    "retention",
    "backups",
]


class InstanceSettingSpecResponse(BaseModel):
    key: str
    group: SettingGroup
    label: str
    description: str
    kind: SettingKind
    default: Any = None
    options: list[str] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None
    secret: bool = False
    restart_required: bool = False


class InstanceSettingResponse(BaseModel):
    key: str
    value: Any = None
    has_value: bool = False
    source: Literal["default", "database", "bootstrap"]
    updated_at: datetime | None = None
    updated_by: str | None = None


class InstanceSettingsResponse(BaseModel):
    specs: list[InstanceSettingSpecResponse]
    values: dict[str, InstanceSettingResponse]


class UpdateInstanceSettingsRequest(BaseModel):
    values: dict[str, Any]


class ResetInstanceSettingsRequest(BaseModel):
    keys: list[str] = Field(default_factory=list)


class TestInstanceSettingsRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class InstanceSettingsTestResponse(BaseModel):
    status: Literal["ok"]
    checked: list[str]
    message: str = ""
