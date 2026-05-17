from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

BACKUPS_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="backup_s3_bucket",
        group="backups",
        label="Backup S3 bucket",
        kind="string",
        default="",
        description="S3-compatible bucket for readable full-instance backups.",
    ),
    SettingSpec(
        key="backup_s3_endpoint_url",
        group="backups",
        label="Backup endpoint URL",
        kind="string",
        default=None,
        description="Optional S3-compatible endpoint URL for Cloudflare R2 or MinIO.",
    ),
    SettingSpec(
        key="backup_s3_region",
        group="backups",
        label="Backup region",
        kind="string",
        default="us-east-1",
        description="S3 region for backup uploads.",
    ),
    SettingSpec(
        key="backup_s3_prefix",
        group="backups",
        label="Backup prefix",
        kind="string",
        default="",
        description="Optional prefix prepended to backup objects.",
    ),
    SettingSpec(
        key="backup_s3_access_key_id",
        group="backups",
        label="Backup access key ID",
        kind="secret",
        default=None,
        description="Optional static access key ID for backup storage.",
        secret=True,
    ),
    SettingSpec(
        key="backup_s3_secret_access_key",
        group="backups",
        label="Backup secret access key",
        kind="secret",
        default=None,
        description="Optional static secret access key for backup storage.",
        secret=True,
    ),
    SettingSpec(
        key="backup_s3_force_path_style",
        group="backups",
        label="Backup path-style requests",
        kind="bool",
        default=False,
        description="Use path-style bucket addressing for backup storage.",
    ),
)
