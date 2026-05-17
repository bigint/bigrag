from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

QUEUE_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="queue_max_depth",
        group="queue",
        label="Queue max depth",
        kind="int",
        default=10000,
        description="Maximum pending ingestion jobs before uploads are rejected.",
        min=1,
        max=10000000,
    ),
)
