from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

RETENTION_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="query_log_retention_days",
        group="retention",
        label="Query log retention",
        kind="int",
        default=90,
        description="Days to keep query logs.",
        min=1,
        max=3650,
    ),
    SettingSpec(
        key="access_log_retention_days",
        group="retention",
        label="Access log retention",
        kind="int",
        default=90,
        description="Days to keep access logs.",
        min=1,
        max=3650,
    ),
    SettingSpec(
        key="webhook_delivery_retention_days",
        group="retention",
        label="Webhook delivery retention",
        kind="int",
        default=90,
        description="Days to keep webhook delivery attempts.",
        min=1,
        max=3650,
    ),
    SettingSpec(
        key="upload_session_item_retention_hours",
        group="retention",
        label="Upload session retention",
        kind="int",
        default=168,
        description="Hours to keep upload-session item history.",
        min=1,
        max=87600,
    ),
    SettingSpec(
        key="embedding_cache_retention_days",
        group="retention",
        label="Embedding cache retention",
        kind="int",
        default=30,
        description="Days to keep persistent embedding-cache rows after last use.",
        min=0,
        max=3650,
    ),
    SettingSpec(
        key="embedding_cache_max_rows",
        group="retention",
        label="Embedding cache max rows",
        kind="int",
        default=0,
        description=(
            "Maximum embedding-cache rows to keep (0 = unlimited); "
            "least-recently-used rows are evicted."
        ),
        min=0,
        max=1000000000,
    ),
)
