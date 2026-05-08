export type Collection = {
  id: string;
  name: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  dimension: number;
  tenant_field: string | null;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  has_api_key: boolean;
  embedding_preset_id: string | null;
  reranking_enabled: boolean;
  reranking_model: string;
  has_reranking_api_key: boolean;
  default_top_k: number;
  default_min_score: number | null;
  default_search_mode: "semantic" | "keyword" | "hybrid";
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CollectionStats = {
  collection: string;
  document_count: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
  status_counts: Record<string, number>;
};

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export type DocumentProgress = {
  document_id: string;
  collection_name: string;
  step: string;
  status: string;
  message: string;
  progress: number;
  detail: Record<string, unknown>;
};

export type Document = {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  progress: DocumentProgress | null;
};

export type UploadSessionItem = {
  id: string;
  client_item_id: string;
  document_id: string | null;
  filename: string;
  file_type: string;
  file_size: number;
  content_hash: string | null;
  status: "queued" | "ingesting" | "complete" | "failed" | "canceled";
  document_status: DocumentStatus | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type UploadSession = {
  id: string;
  collection_id: string;
  collection_name: string;
  status: "preparing" | "uploading" | "ingesting" | "complete" | "failed" | "canceled";
  total_files: number;
  total_bytes: number;
  uploaded_files: number;
  queued_files: number;
  processing_files: number;
  completed_files: number;
  failed_files: number;
  canceled_files: number;
  active_files: number;
  recent_items: UploadSessionItem[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
};

export type UploadSessionFileResponse = {
  item: UploadSessionItem;
  session: UploadSession;
};

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
  details: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type InstanceSettingKind =
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
  | "rate_limits"
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
  restart_required: boolean;
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

export type Chunk = {
  id: string;
  text: string;
  document_id: string;
  chunk_index: number;
  metadata: Record<string, unknown>;
};

export type QueryResult = {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  page_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  metadata: Record<string, unknown>;
};

export type QueryTimings = {
  embed_ms: number;
  search_ms: number;
  rerank_ms: number;
  total_ms: number;
};

export type QueryResponse = {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
  timings?: QueryTimings;
};

export type ChatSource = {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  document_filename: string | null;
  chunk_index: number | null;
  page_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  metadata: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "complete" | "error";
  error_message: string | null;
  model_provider: string | null;
  model: string | null;
  retrieval: Record<string, unknown>;
  sources: ChatSource[];
  created_at: string;
};

export type ChatConversation = {
  id: string;
  title: string;
  collection: string | null;
  model_provider: string;
  model: string;
  temperature: number;
  top_k: number;
  search_mode: "semantic" | "keyword" | "hybrid" | string;
  min_score: number | null;
  rerank: boolean | null;
  message_count: number;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
};

export type ChatListResponse = {
  conversations: ChatConversation[];
  total: number;
};

export type ChatDetailResponse = {
  conversation: ChatConversation;
  messages: ChatMessage[];
};

export type ChatCreateBody = {
  message: string;
  conversation_id?: string | null;
  collection?: string | null;
  stream?: boolean;
  model_provider?: "openai" | "openai_compatible";
  model?: string;
  temperature?: number;
  top_k?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  min_score?: number | null;
  rerank?: boolean | null;
  filters?: Record<string, unknown> | null;
  system_prompt?: string;
  provider_api_key?: string;
  provider_base_url?: string | null;
};

export type ChatCreateResponse = {
  conversation: ChatConversation;
  message: ChatMessage;
  assistant_message: ChatMessage;
  sources: ChatSource[];
  timings?: QueryTimings | null;
};

export type EmbeddingPreset = {
  id: string;
  name: string;
  provider: "openai" | "cohere" | "voyage";
  model: string;
  base_url: string | null;
  dimension: number;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
};

export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  active: boolean;
  scopes: string[];
  collection: string | null;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatedApiKey = ApiKey & { key: string };

export type McpServer = {
  id: string;
  title: string;
  server_name: string;
  collection: string | null;
  key_prefix: string;
  key_active: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatedMcpServer = McpServer & { api_key: string };

export type Webhook = {
  id: string;
  url: string;
  events: string[];
  collections: string[] | null;
  description: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type PlatformStats = {
  collections: number;
  documents: {
    total: number;
    ready: number;
    pending: number;
    processing: number;
    failed: number;
    total_chunks: number;
    total_tokens: number;
    total_size_bytes: number;
  };
  webhooks: number;
  queue: Record<string, number>;
};

export type ReadinessReport = {
  version: string;
  postgres: boolean;
  qdrant: boolean | null;
  vector_store: boolean;
  vector_store_provider: "qdrant" | "s3_vectors" | "turbopuffer";
  redis: boolean;
  embedding: boolean;
  embedding_error?: string;
  embedding_source?: "env" | "preset" | "collection";
  status: "ok" | "degraded";
};

export type AccessLogEntry = {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  api_key_id: string | null;
  api_key_name: string | null;
  auth_method: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  collection_name: string | null;
  method: string;
  path: string;
  route: string | null;
  status_code: number;
  success: boolean;
  latency_ms: number;
  request_id: string | null;
  metadata: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
};

type AccessLogBucket = {
  label: string;
  count: number;
  avg_latency_ms?: number | null;
};

type AccessLogTimelinePoint = {
  bucket: string;
  events: number;
  errors: number;
  avg_latency_ms: number;
};

export type AccessLogOverview = {
  window_days: number;
  total_events: number;
  success_rate: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  unique_users: number;
  query_events: number;
  by_action: AccessLogBucket[];
  latency_by_action: AccessLogBucket[];
  timeline: AccessLogTimelinePoint[];
  recent: AccessLogEntry[];
};

export type AccessLogListResponse = {
  entries: AccessLogEntry[];
  total: number;
};
