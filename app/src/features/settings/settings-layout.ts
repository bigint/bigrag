import type {
  InstanceSettingGroup,
  InstanceSettingSpec,
  InstanceSettingValue,
} from "@/types/bigrag";

export type SettingsGroupLayout = {
  readonly group: InstanceSettingGroup;
  readonly title: string;
  readonly eyebrow: string;
  readonly description: string;
  readonly recommendedAction: string;
  readonly emptyState: string;
  readonly commonKeys: readonly string[];
  readonly dangerKeys?: readonly string[];
};

export type SettingsStatusSummary = {
  readonly total: number;
  readonly common: number;
  readonly advanced: number;
  readonly overrides: number;
  readonly secrets: number;
  readonly missingSecrets: number;
};

const SETTINGS_GROUP_LAYOUTS: Record<InstanceSettingGroup, SettingsGroupLayout> = {
  backups: {
    commonKeys: [
      "backup_s3_bucket",
      "backup_s3_endpoint_url",
      "backup_s3_region",
      "backup_s3_prefix",
      "backup_s3_access_key_id",
      "backup_s3_secret_access_key",
    ],
    description: "Readable full-instance exports to S3, R2, or MinIO.",
    emptyState: "Backup destination settings are not available from this API.",
    eyebrow: "Disaster recovery",
    group: "backups",
    recommendedAction: "Configure the destination, save it, then start a readable export.",
    title: "Backup destination",
  },
  chat: {
    commonKeys: ["chat_provider", "chat_model", "chat_base_url", "chat_temperature"],
    description: "Default provider and behavior for stored chat conversations.",
    emptyState: "Chat runtime settings are not available from this API.",
    eyebrow: "Answering",
    group: "chat",
    recommendedAction: "Keep defaults conservative, then tune model behavior per deployment.",
    title: "Chat defaults",
  },
  ingestion: {
    commonKeys: [
      "max_upload_size_mb",
      "max_batch_upload_size_mb",
      "upload_session_upload_concurrency",
      "conversion_pdf_ocr_enabled",
      "conversion_timeout",
      "ingestion_workers",
      "ingestion_batch_size",
    ],
    description: "Upload, conversion, OCR, and worker limits for document intake.",
    emptyState: "Ingestion settings are not available from this API.",
    eyebrow: "Document intake",
    group: "ingestion",
    recommendedAction: "Set practical upload limits before changing raw vector caps.",
    title: "Ingestion",
  },
  queue: {
    commonKeys: ["queue_max_depth"],
    description: "Backpressure for ingestion jobs before uploads are rejected.",
    emptyState: "Queue settings are not available from this API.",
    eyebrow: "Backpressure",
    group: "queue",
    recommendedAction: "Increase only when workers and Redis capacity are sized for the load.",
    title: "Queue",
  },
  retention: {
    commonKeys: [
      "query_log_retention_days",
      "access_log_retention_days",
      "webhook_delivery_retention_days",
      "progress_snapshot_retention_days",
      "upload_session_item_retention_hours",
      "embedding_cache_retention_days",
      "audit_log_retention_days",
    ],
    description: "How long operational logs and temporary histories stay available.",
    emptyState: "Retention settings are not available from this API.",
    eyebrow: "Data lifecycle",
    group: "retention",
    recommendedAction: "Balance debugging history with storage and privacy requirements.",
    title: "Retention",
  },
  search: {
    commonKeys: [
      "embedding_provider",
      "embedding_model",
      "embedding_dimension",
      "embedding_api_key",
      "embedding_base_url",
      "embedding_concurrency",
    ],
    description: "Fallback embedding defaults and retrieval cache behavior.",
    emptyState: "Search runtime settings are not available from this API.",
    eyebrow: "Retrieval",
    group: "search",
    recommendedAction: "Set provider defaults here, then override per collection when needed.",
    title: "Embedding and search",
  },
  security: {
    commonKeys: ["trusted_proxies", "embedding_cache_mode"],
    dangerKeys: [
      "allow_public_bind_in_prod",
      "allow_private_embedding_base_urls",
      "allow_private_chat_base_urls",
      "allow_local_webhooks",
    ],
    description: "Trusted proxy handling, outbound URL policy, and cache posture.",
    emptyState: "Security settings are not available from this API.",
    eyebrow: "Access and policy",
    group: "security",
    recommendedAction: "Keep outbound provider access narrow before widening network policy.",
    title: "Security posture",
  },
  storage: {
    commonKeys: [
      "storage_backend",
      "storage_s3_bucket",
      "storage_s3_endpoint_url",
      "storage_s3_region",
      "storage_s3_prefix",
      "storage_s3_access_key_id",
      "storage_s3_secret_access_key",
      "storage_s3_force_path_style",
    ],
    description: "Where uploaded source files are stored and retrieved.",
    emptyState: "Storage settings are not available from this API.",
    eyebrow: "Files",
    group: "storage",
    recommendedAction:
      "Choose local storage for development and S3-compatible storage for production.",
    title: "File storage",
  },
  vector_store: {
    commonKeys: [
      "qdrant_url",
      "qdrant_connect_timeout_seconds",
      "qdrant_required",
      "qdrant_search_ef",
      "turbopuffer_api_key",
      "turbopuffer_region",
      "turbopuffer_namespace_prefix",
    ],
    description: "Vector backend connection details and provider credentials.",
    emptyState: "Vector storage settings are not available from this API.",
    eyebrow: "Indexes",
    group: "vector_store",
    recommendedAction: "Keep connection details ready for the providers collections can select.",
    title: "Vector storage",
  },
  webhooks: {
    commonKeys: ["webhook_delivery_timeout", "webhook_retry_delays", "webhook_max_count"],
    description: "Delivery limits and retry cadence for outbound webhook events.",
    emptyState: "Webhook settings are not available from this API.",
    eyebrow: "Outbound events",
    group: "webhooks",
    recommendedAction: "Tune retry windows to match receiver reliability.",
    title: "Webhooks",
  },
};

export const getSettingsGroupLayout = (group: InstanceSettingGroup): SettingsGroupLayout =>
  SETTINGS_GROUP_LAYOUTS[group];

export const splitSettingsByImportance = (
  specs: readonly InstanceSettingSpec[],
  layout: SettingsGroupLayout,
) => {
  const commonKeys = new Set(layout.commonKeys);
  return {
    advanced: specs.filter((spec) => !commonKeys.has(spec.key)),
    common: specs.filter((spec) => commonKeys.has(spec.key)),
  };
};

export const settingsStatusSummary = (
  specs: readonly InstanceSettingSpec[],
  values: Readonly<Record<string, InstanceSettingValue | undefined>>,
  layout: SettingsGroupLayout,
): SettingsStatusSummary => {
  const { advanced, common } = splitSettingsByImportance(specs, layout);
  return {
    advanced: advanced.length,
    common: common.length,
    missingSecrets: specs.filter((spec) => spec.secret && !values[spec.key]?.has_value).length,
    overrides: specs.filter((spec) => values[spec.key]?.source === "database").length,
    secrets: specs.filter((spec) => spec.secret).length,
    total: specs.length,
  };
};

export const settingsRecommendedAction = (
  layout: SettingsGroupLayout,
  summary: SettingsStatusSummary,
): string => {
  if (summary.missingSecrets > 0 && (layout.group === "backups" || layout.group === "storage")) {
    return "Add the missing credentials, then save the connection.";
  }
  return layout.recommendedAction;
};
