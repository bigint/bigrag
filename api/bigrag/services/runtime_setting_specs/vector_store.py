from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

VECTOR_STORE_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="qdrant_url",
        group="vector_store",
        label="Qdrant URL",
        kind="string",
        default="http://localhost:6333",
        description="Qdrant connection URL.",
    ),
    SettingSpec(
        key="qdrant_connect_timeout_seconds",
        group="vector_store",
        label="Qdrant connect timeout",
        kind="int",
        default=10,
        description="Qdrant startup connection timeout in seconds.",
        min=0,
        max=300,
    ),
    SettingSpec(
        key="qdrant_required",
        group="vector_store",
        label="Require vector store",
        kind="bool",
        default=False,
        description="Fail startup if configured vector-store clients cannot be reached.",
    ),
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
    SettingSpec(
        key="qdrant_search_ef",
        group="vector_store",
        label="Qdrant search ef",
        kind="int",
        default=None,
        description="Optional Qdrant HNSW search ef override.",
        min=1,
        max=10000,
    ),
)
