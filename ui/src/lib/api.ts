const BASE_URL = process.env.NEXT_PUBLIC_BIGRAG_URL || "http://localhost:8080";
const API_KEY = process.env.NEXT_PUBLIC_BIGRAG_API_KEY || "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}),
    ...((options.headers as Record<string, string>) || {})
  };

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    cache: "no-store",
    headers
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body?.error?.message || res.statusText,
      body?.error?.code
    );
  }

  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function getHealth() {
  return request<{ status: string; version: string }>("/health");
}

// ---------------------------------------------------------------------------
// Namespaces
// ---------------------------------------------------------------------------

export interface NamespaceListItem {
  id: string;
}

export interface NamespaceListResponse {
  namespaces: NamespaceListItem[];
  next_cursor?: string;
}

export async function listNamespaces(
  prefix?: string,
  cursor?: string,
  pageSize = 100
) {
  const params = new URLSearchParams();
  if (prefix) params.set("prefix", prefix);
  if (cursor) params.set("cursor", cursor);
  params.set("page_size", String(pageSize));
  return request<NamespaceListResponse>(`/v1/namespaces?${params}`);
}

export interface NamespaceMetadata {
  schema: Record<string, unknown>;
  approx_logical_bytes: number;
  approx_row_count: number;
  created_at: string;
  updated_at: string;
  index: { status: string; unindexed_bytes?: number };
}

export async function getNamespaceMetadata(ns: string) {
  return request<NamespaceMetadata>(
    `/v1/namespaces/${encodeURIComponent(ns)}/metadata`
  );
}

export async function deleteNamespace(ns: string) {
  return request<{ status: string }>(
    `/v2/namespaces/${encodeURIComponent(ns)}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export async function getSchema(ns: string) {
  return request<Record<string, unknown>>(
    `/v1/namespaces/${encodeURIComponent(ns)}/schema`
  );
}

export async function updateSchema(
  ns: string,
  schema: Record<string, unknown>
) {
  return request<{ status: string }>(
    `/v1/namespaces/${encodeURIComponent(ns)}/schema`,
    { body: JSON.stringify(schema), method: "PUT" }
  );
}

// ---------------------------------------------------------------------------
// Documents — Write
// ---------------------------------------------------------------------------

export interface WriteRequest {
  upsert_rows?: Record<string, unknown>[];
  upsert_columns?: Record<string, unknown>;
  patch_rows?: Record<string, unknown>[];
  patch_columns?: Record<string, unknown>;
  deletes?: (string | number)[];
  delete_by_filter?: {
    filter: unknown;
    max_affected?: number;
    allow_partial?: boolean;
  };
  patch_by_filter?: {
    filter: unknown;
    attributes: Record<string, unknown>;
    max_affected?: number;
    allow_partial?: boolean;
  };
  distance_metric?: string;
  schema?: Record<string, unknown>;
  return_affected_ids?: boolean;
  condition?: unknown;
  copy_from_namespace?: string | { namespace: string };
}

export interface WriteResponse {
  rows_affected: number;
  rows_upserted?: number;
  rows_patched?: number;
  rows_deleted?: number;
  rows_skipped?: number;
  rows_remaining?: boolean;
  upserted_ids?: unknown[];
  patched_ids?: unknown[];
  deleted_ids?: unknown[];
  billing: Record<string, unknown>;
  performance: { server_total_ms: number };
}

export async function writeDocuments(ns: string, body: WriteRequest) {
  return request<WriteResponse>(`/v2/namespaces/${encodeURIComponent(ns)}`, {
    body: JSON.stringify(body),
    method: "POST"
  });
}

// ---------------------------------------------------------------------------
// Documents — Query
// ---------------------------------------------------------------------------

export interface QueryRequest {
  rank_by?: unknown;
  filters?: unknown;
  top_k?: number;
  limit?: unknown;
  include_attributes?: unknown;
  exclude_attributes?: string[];
  aggregations?: unknown[];
  cursor?: string;
  queries?: QueryRequest[];
  include_vectors?: boolean;
  vector_encoding?: string;
}

export interface QueryRow {
  id: string | number;
  $dist?: number;
  [key: string]: unknown;
}

export interface QueryResponse {
  rows?: QueryRow[];
  results?: QueryResponse[];
  aggregations?: Record<string, unknown>;
  next_cursor?: string;
  billing: Record<string, unknown>;
  performance: Record<string, unknown>;
}

export async function queryDocuments(ns: string, body: QueryRequest) {
  return request<QueryResponse>(
    `/v2/namespaces/${encodeURIComponent(ns)}/query`,
    { body: JSON.stringify(body), method: "POST" }
  );
}

// ---------------------------------------------------------------------------
// Documents — Explain Query
// ---------------------------------------------------------------------------

export interface ExplainResult {
  namespace: string;
  total_documents: number;
  has_rank_by: boolean;
  has_filters: boolean;
  rank_by_type?: string;
  limit: number;
  strategy: string;
  estimated_cost: string;
}

export async function explainQuery(ns: string, body: QueryRequest) {
  return request<ExplainResult>(
    `/v2/namespaces/${encodeURIComponent(ns)}/explain_query`,
    { body: JSON.stringify(body), method: "POST" }
  );
}

// ---------------------------------------------------------------------------
// Documents — Single Document
// ---------------------------------------------------------------------------

export async function getDocument(ns: string, id: string) {
  return request<Record<string, unknown>>(
    `/v1/namespaces/${encodeURIComponent(ns)}/documents/${encodeURIComponent(id)}`
  );
}

// ---------------------------------------------------------------------------
// Export & Copy
// ---------------------------------------------------------------------------

export interface ExportResponse {
  format: string;
  document_count: number;
  data: string;
}

export async function exportNamespace(ns: string) {
  return request<ExportResponse>(
    `/v1/namespaces/${encodeURIComponent(ns)}/export`,
    { body: JSON.stringify({}), method: "POST" }
  );
}

export interface CopyResponse {
  status: string;
  source_namespace: string;
  destination_namespace: string;
  documents_copied: number;
}

export async function copyNamespace(
  destination: string,
  sourceNamespace: string
) {
  return request<CopyResponse>(
    `/v1/namespaces/${encodeURIComponent(destination)}/copy`,
    {
      body: JSON.stringify({ source_namespace: sourceNamespace }),
      method: "POST"
    }
  );
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export async function getAdminConfig() {
  return request<Record<string, unknown>>("/v1/admin/config");
}

export async function triggerCompaction(ns: string) {
  return request<{ status: string; message: string }>(
    `/v1/admin/compact/${encodeURIComponent(ns)}`,
    { method: "POST" }
  );
}

export async function triggerWarm(ns: string) {
  return request<{ status: string; message: string }>(
    `/v1/admin/warm/${encodeURIComponent(ns)}`,
    { method: "POST" }
  );
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export interface ApiKeyPermissions {
  namespaces: string[];
  operations: string[];
  admin: boolean;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  permissions: ApiKeyPermissions;
  created_at: string;
  last_used_at?: string;
  expires_at?: string;
}

export interface CreateApiKeyRequest {
  name: string;
  namespaces?: string[];
  operations?: string[];
  admin?: boolean;
  expires_at?: string;
}

export interface CreateApiKeyResponse {
  key: string;
  id: string;
  name: string;
  prefix: string;
  permissions: ApiKeyPermissions;
  created_at: string;
  expires_at?: string;
}

export async function createApiKey(body: CreateApiKeyRequest) {
  return request<CreateApiKeyResponse>("/v1/admin/api-keys", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function listApiKeys() {
  return request<{ keys: ApiKeySummary[] }>("/v1/admin/api-keys");
}

export async function revokeApiKey(id: string) {
  return request<{ status: string; message: string }>(
    `/v1/admin/api-keys/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Debug
// ---------------------------------------------------------------------------

export interface RecallResult {
  avg_recall: number;
  samples: number;
  top_k: number;
  total_vectors: number;
  note?: string;
}

export async function debugRecall(ns: string, num?: number, topK?: number) {
  return request<RecallResult>(
    `/v1/namespaces/${encodeURIComponent(ns)}/_debug/recall`,
    {
      body: JSON.stringify({
        num: num ?? 25,
        top_k: topK ?? 10
      }),
      method: "POST"
    }
  );
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

export async function getMetrics() {
  const res = await fetch(`${BASE_URL}/v1/metrics`, {
    cache: "no-store",
    headers: API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}
  });
  return res.text();
}
