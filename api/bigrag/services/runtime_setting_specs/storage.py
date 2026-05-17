from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

STORAGE_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="storage_backend",
        group="storage",
        label="Storage backend",
        kind="select",
        default="local",
        description="Document binary storage backend.",
        options=("local", "s3"),
    ),
    SettingSpec(
        key="storage_s3_bucket",
        group="storage",
        label="S3 bucket",
        kind="string",
        default="",
        description="Bucket used when the storage backend is S3 or MinIO.",
    ),
    SettingSpec(
        key="storage_s3_endpoint_url",
        group="storage",
        label="S3 endpoint URL",
        kind="string",
        default=None,
        description="Optional MinIO or S3-compatible endpoint URL.",
    ),
    SettingSpec(
        key="storage_s3_region",
        group="storage",
        label="S3 region",
        kind="string",
        default="us-east-1",
        description="S3 region for bucket operations.",
    ),
    SettingSpec(
        key="storage_s3_prefix",
        group="storage",
        label="S3 prefix",
        kind="string",
        default="",
        description="Optional key prefix prepended to uploaded documents.",
    ),
    SettingSpec(
        key="storage_s3_access_key_id",
        group="storage",
        label="S3 access key ID",
        kind="secret",
        default=None,
        description="Optional static access key ID for S3-compatible storage.",
        secret=True,
    ),
    SettingSpec(
        key="storage_s3_secret_access_key",
        group="storage",
        label="S3 secret access key",
        kind="secret",
        default=None,
        description="Optional static secret access key for S3-compatible storage.",
        secret=True,
    ),
    SettingSpec(
        key="storage_s3_force_path_style",
        group="storage",
        label="S3 path-style requests",
        kind="bool",
        default=False,
        description="Use path-style bucket addressing for MinIO.",
    ),
)
