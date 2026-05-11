export type GoogleConnectorConfig = {
  provider: "google_drive";
  configured: boolean;
  enabled: boolean;
  client_id: string;
  has_client_secret: boolean;
  callback_url: string;
  created_at: string | null;
  updated_at: string | null;
};

export type GoogleAccount = {
  provider: "google_drive";
  configured: boolean;
  connected: boolean;
  status: "pending" | "connected" | "needs_reauth" | "revoked" | null;
  email: string | null;
  scopes: string[];
  token_expires_at: string | null;
  last_connected_at: string | null;
};

export type GoogleDriveFile = {
  id: string;
  name: string;
  mime_type: string;
  source_type: "file" | "folder";
  modified_time: string | null;
  size: number | null;
  web_url: string | null;
  sync_supported: boolean;
  unsupported_reason: string | null;
};

export type GoogleDriveFileList = {
  provider: "google_drive";
  parent_id: string;
  query: string;
  files: GoogleDriveFile[];
  next_page_token: string | null;
};

export type GoogleSyncProgressPhase =
  | "queued"
  | "authenticating"
  | "scanning"
  | "syncing"
  | "removing"
  | "finalizing"
  | "complete"
  | "failed";

export type GoogleSyncProgress = {
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
};

export type GoogleSyncJobDetails = Record<string, unknown> & {
  errors?: Array<Record<string, string>>;
  progress?: GoogleSyncProgress;
};

export type GoogleDriveSource = {
  id: string;
  provider: "google_drive";
  collection_name: string;
  root_id: string;
  root_name: string;
  root_mime_type: string;
  source_type: "file" | "folder";
  status: "idle" | "syncing" | "needs_reauth" | "error";
  schedule_enabled: boolean;
  sync_interval_hours: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
  last_error: string | null;
  account_email: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type GoogleDriveSyncJob = {
  id: string;
  provider: "google_drive";
  source_id: string | null;
  trigger: "initial" | "manual" | "scheduled";
  status: "pending" | "running" | "complete" | "failed";
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
};
