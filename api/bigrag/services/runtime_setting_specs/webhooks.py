from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

WEBHOOKS_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="webhook_delivery_timeout",
        group="webhooks",
        label="Delivery timeout",
        kind="int",
        default=10,
        description="Webhook delivery timeout in seconds.",
        min=1,
        max=300,
    ),
    SettingSpec(
        key="webhook_retry_delays",
        group="webhooks",
        label="Retry delays",
        kind="int_list",
        default=[10, 30, 90],
        description="Webhook retry delays in seconds.",
    ),
    SettingSpec(
        key="webhook_max_count",
        group="webhooks",
        label="Max webhooks",
        kind="int",
        default=50,
        description="Maximum configured webhooks per instance.",
        min=0,
        max=10000,
    ),
)
