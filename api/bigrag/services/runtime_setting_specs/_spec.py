from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bigrag.models.instance_settings import SettingGroup, SettingKind

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
