export type GoogleProvider = "google_drive";
export type ConnectorAccountStatus = "pending" | "connected" | "needs_reauth" | "revoked";
export type ConnectorSourceStatus = "idle" | "syncing" | "needs_reauth" | "error";
export type ConnectorSourceType = "file" | "folder";
export type ConnectorSyncTrigger = "initial" | "manual" | "scheduled";
export type ConnectorSyncStatus = "pending" | "running" | "complete" | "failed";
export type GoogleSyncProgressPhase =
  | "queued"
  | "authenticating"
  | "scanning"
  | "syncing"
  | "removing"
  | "finalizing"
  | "complete"
  | "failed";

export interface GoogleSyncProgress {
  phase: GoogleSyncProgressPhase;
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

export type GoogleSyncJobDetails = Record<string, unknown> & {
  errors?: Array<Record<string, string>>;
  progress?: GoogleSyncProgress;
};

export interface GoogleConnectorConfig {
  provider: GoogleProvider;
  configured: boolean;
  enabled: boolean;
  client_id: string;
  has_client_secret: boolean;
  callback_url: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface UpdateGoogleConnectorConfigBody {
  enabled?: boolean;
  client_id?: string;
  client_secret?: string | null;
}

export interface GoogleAccount {
  provider: GoogleProvider;
  configured: boolean;
  connected: boolean;
  status: ConnectorAccountStatus | null;
  email: string | null;
  scopes: string[];
  token_expires_at: string | null;
  last_connected_at: string | null;
}

export interface GoogleDriveFile {
  id: string;
  name: string;
  mime_type: string;
  source_type: ConnectorSourceType;
  modified_time: string | null;
  size: number | null;
  web_url: string | null;
  sync_supported: boolean;
  unsupported_reason: string | null;
}

export interface GoogleDriveFileListResponse {
  provider: GoogleProvider;
  parent_id: string;
  query: string;
  files: GoogleDriveFile[];
  next_page_token: string | null;
}

export interface GoogleOAuthStartUrlResponse {
  auth_url: string;
}

export interface CreateGoogleSourceBody {
  collection_name: string;
  root_id: string;
  root_name: string;
  root_mime_type?: string;
  source_type?: ConnectorSourceType | null;
  metadata?: Record<string, unknown>;
}

export interface UpdateGoogleSourceBody {
  schedule_enabled?: boolean | null;
  sync_interval_hours?: number | null;
}

export interface GoogleSource {
  id: string;
  provider: GoogleProvider;
  collection_name: string;
  root_id: string;
  root_name: string;
  root_mime_type: string;
  source_type: ConnectorSourceType;
  status: ConnectorSourceStatus;
  schedule_enabled: boolean;
  sync_interval_hours: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
  last_error: string | null;
  account_email: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface GoogleSourceListResponse {
  sources: GoogleSource[];
  total: number;
}

export interface GoogleSyncJob {
  id: string;
  provider: GoogleProvider;
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
  details: GoogleSyncJobDetails;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoogleSyncJobListResponse {
  jobs: GoogleSyncJob[];
  total: number;
}
