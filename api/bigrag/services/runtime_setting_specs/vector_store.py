from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

VECTOR_STORE_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="turbopuffer_api_key",
        group="vector_store",
        label="turbopuffer API key",
        kind="secret",
        default=None,
        description="turbopuffer API key.",
        secret=True,
    ),
    SettingSpec(
        key="turbopuffer_base_url",
        group="vector_store",
        label="turbopuffer base URL",
        kind="string",
        default=None,
        description="Optional turbopuffer API base URL.",
    ),
    SettingSpec(
        key="turbopuffer_region",
        group="vector_store",
        label="turbopuffer region",
        kind="string",
        default="aws-us-east-1",
        description="turbopuffer region slug.",
    ),
    SettingSpec(
        key="turbopuffer_namespace_prefix",
        group="vector_store",
        label="turbopuffer namespace prefix",
        kind="string",
        default="bigrag_",
        description="Prefix prepended to turbopuffer namespace names.",
    ),
)
