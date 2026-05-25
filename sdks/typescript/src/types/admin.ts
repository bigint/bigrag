import type { User } from "./auth.js";

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
  | "vector_store"
  | "queue"
  | "search"
  | "chat"
  | "webhooks"
  | "retention";

export interface InstanceSettingSpec {
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
}

export interface InstanceSetting {
  key: string;
  value: unknown;
  has_value: boolean;
  source: "default" | "database" | "bootstrap";
  updated_at: string | null;
  updated_by: string | null;
}

export interface InstanceSettingsResponse {
  specs: InstanceSettingSpec[];
  values: Record<string, InstanceSetting>;
}

export interface UpdateInstanceSettingsBody {
  values: Record<string, unknown>;
}

export interface ResetInstanceSettingsBody {
  keys: string[];
}

export interface TestInstanceSettingsBody {
  values?: Record<string, unknown>;
}

export interface InstanceSettingsTestResponse {
  status: "ok";
  checked: string[];
  message: string;
}

export interface VectorStorageHealth {
  status: "ok" | "error";
  error: string | null;
}

export interface VectorStorageCollection {
  name: string;
  documents: number;
  chunks: number;
  bytes: number;
}

export interface VectorStorageTotals {
  collections: number;
  documents: number;
  chunks: number;
  bytes: number;
}

export interface VectorStorageOverviewResponse {
  provider: string;
  health: VectorStorageHealth;
  collections: VectorStorageCollection[];
  totals: VectorStorageTotals;
}

export interface UserListResponse {
  users: User[];
  total: number;
}

export interface CreateUserBody {
  email: string;
  password: string;
  display_name?: string;
  role?: string;
}

export interface UpdateUserBody {
  email?: string;
  display_name?: string;
  role?: string;
  password?: string;
}

export interface ApiKey {
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
}

export interface CreateApiKeyBody {
  name: string;
  expires_at?: string | null;
  scopes?: string[] | null;
  collection?: string | null;
}

export interface CreateApiKeyResponse extends ApiKey {
  key: string;
}

export interface UpdateApiKeyBody {
  name?: string;
  active?: boolean;
  expires_at?: string | null;
  scopes?: string[] | null;
  collection?: string | null;
}

export interface ApiKeyListResponse {
  keys: ApiKey[];
  total: number;
}

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  api_key_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  entries: AuditLogEntry[];
  total: number;
}

export interface EmbeddingPreset {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url: string | null;
  dimension: number;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateEmbeddingPresetBody {
  name: string;
  provider: string;
  model: string;
  api_key: string;
  base_url?: string | null;
  dimension: number;
}

export interface UpdateEmbeddingPresetBody {
  name?: string;
  provider?: string;
  model?: string;
  api_key?: string;
  base_url?: string | null;
  dimension?: number;
}

export interface EmbeddingPresetListResponse {
  presets: EmbeddingPreset[];
  total: number;
}

export interface McpServer {
  id: string;
  title: string;
  server_name: string;
  collection: string | null;
  key_prefix: string;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateMcpServerBody {
  title: string;
  server_name: string;
  collection?: string | null;
}

export interface UpdateMcpServerBody {
  title?: string;
  server_name?: string;
  collection?: string | null;
}

export interface CreateMcpServerResponse extends McpServer {
  api_key: string;
}

export interface McpServerListResponse {
  servers: McpServer[];
  total: number;
}
