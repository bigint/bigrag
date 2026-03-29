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

// Health
export async function getHealth() {
  return request<{ status: string; version: string }>("/health");
}

// Namespaces
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
    {
      method: "DELETE"
    }
  );
}

// Schema
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
    {
      body: JSON.stringify(schema),
      method: "PUT"
    }
  );
}

// Documents
export interface WriteRequest {
  upsert_rows?: Record<string, unknown>[];
  upsert_columns?: Record<string, unknown>;
  patch_rows?: Record<string, unknown>[];
  deletes?: (string | number)[];
  delete_by_filter?: {
    filter: unknown;
    max_affected?: number;
    allow_partial?: boolean;
  };
  distance_metric?: string;
  schema?: Record<string, unknown>;
}

export interface WriteResponse {
  rows_affected: number;
  rows_upserted?: number;
  rows_patched?: number;
  rows_deleted?: number;
  rows_skipped?: number;
  rows_remaining?: boolean;
  billing: Record<string, unknown>;
  performance: { server_total_ms: number };
}

export async function writeDocuments(ns: string, body: WriteRequest) {
  return request<WriteResponse>(`/v2/namespaces/${encodeURIComponent(ns)}`, {
    body: JSON.stringify(body),
    method: "POST"
  });
}

// Query
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
    {
      body: JSON.stringify(body),
      method: "POST"
    }
  );
}

// Single document
export async function getDocument(ns: string, id: string) {
  return request<Record<string, unknown>>(
    `/v1/namespaces/${encodeURIComponent(ns)}/documents/${encodeURIComponent(id)}`
  );
}

// Admin
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

// Metrics
export async function getMetrics() {
  const res = await fetch(`${BASE_URL}/v1/metrics`, {
    cache: "no-store",
    headers: API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}
  });
  return res.text();
}
