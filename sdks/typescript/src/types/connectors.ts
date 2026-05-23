export type ConnectorProvider = "s3";
export type ConnectorSourceStatus = "idle" | "syncing" | "error";
export type ConnectorSourceType = "prefix";
export type ConnectorSyncTrigger = "initial" | "manual" | "scheduled";
export type ConnectorSyncStatus = "pending" | "running" | "complete" | "failed";
export type ConnectorSyncProgressPhase =
  | "queued"
  | "authenticating"
  | "scanning"
  | "syncing"
  | "removing"
  | "finalizing"
  | "complete"
  | "failed";

export interface ConnectorSyncProgress {
  phase: ConnectorSyncProgressPhase;
  message: string;
  current_item_name: string | null;
  current_item_id: string | null;
  progress_percent: number;
  processed_items: number;
  total_items: number;
  counts: {
    created: number;
    updated: number;
    skipped: number;
    deleted: number;
    failed: number;
  };
}

export type ConnectorSyncJobDetails = Record<string, unknown> & {
  errors?: Array<Record<string, string>>;
  progress?: ConnectorSyncProgress;
};

export interface CreateS3SourceBody {
  collection_name: string;
  bucket: string;
  prefix?: string;
  region?: string;
  endpoint_url?: string | null;
  force_path_style?: boolean;
  access_key_id: string;
  secret_access_key: string;
  session_token?: string | null;
  schedule_enabled?: boolean;
  sync_interval_hours?: number;
  metadata?: Record<string, unknown>;
}

export interface UpdateS3SourceBody {
  bucket?: string | null;
  prefix?: string | null;
  region?: string | null;
  endpoint_url?: string | null;
  force_path_style?: boolean | null;
  access_key_id?: string | null;
  secret_access_key?: string | null;
  session_token?: string | null;
  schedule_enabled?: boolean | null;
  sync_interval_hours?: number | null;
  metadata?: Record<string, unknown> | null;
}

export interface S3Source {
  id: string;
  provider: ConnectorProvider;
  collection_name: string;
  bucket: string;
  prefix: string;
  region: string;
  endpoint_url: string | null;
  force_path_style: boolean;
  has_credentials: boolean;
  root_id: string;
  root_name: string;
  source_type: ConnectorSourceType;
  status: ConnectorSourceStatus;
  schedule_enabled: boolean;
  sync_interval_hours: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
  last_error: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface S3SourceListResponse {
  sources: S3Source[];
  total: number;
}

export interface S3SyncJob {
  id: string;
  provider: ConnectorProvider;
  source_id: string | null;
  trigger: ConnectorSyncTrigger;
  status: ConnectorSyncStatus;
  total_found: number;
  total_created: number;
  total_updated: number;
  total_skipped: number;
  total_deleted: number;
  total_failed: number;
  error_message: string | null;
  details: ConnectorSyncJobDetails;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface S3SyncJobListResponse {
  jobs: S3SyncJob[];
  total: number;
}
