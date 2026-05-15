type InstanceSettingKind =
  | "bool"
  | "int"
  | "float"
  | "string"
  | "string_list"
  | "int_list"
  | "select"
  | "secret";

export type InstanceSettingGroup =
  | "security"
  | "ingestion"
  | "storage"
  | "vector_store"
  | "queue"
  | "search"
  | "chat"
  | "webhooks"
  | "retention"
  | "backups";

export type InstanceSettingSpec = {
  key: string;
  group: InstanceSettingGroup;
  label: string;
  description: string;
  kind: InstanceSettingKind;
  default: unknown;
  options: string[];
  min: number | null;
  max: number | null;
  secret: boolean;
};

export type InstanceSettingValue = {
  key: string;
  value: unknown;
  has_value: boolean;
  source: "default" | "database" | "bootstrap";
  updated_at: string | null;
  updated_by: string | null;
};

export type InstanceSettingsResponse = {
  specs: InstanceSettingSpec[];
  values: Record<string, InstanceSettingValue>;
};

export type BackupJob = {
  id: string;
  label: string;
  status: "pending" | "running" | "succeeded" | "failed";
  progress: number;
  destination_prefix: string;
  object_count: number;
  byte_count: number;
  manifest: Record<string, unknown>;
  error_message: string | null;
  created_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BackupJobListResponse = {
  jobs: BackupJob[];
  total: number;
};
