import { clearAuth, getBaseUrl, getSessionToken } from "./auth-store";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getSessionToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {})
  };

  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    cache: "no-store",
    headers
  });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/v1/auth/")) {
      clearAuth();
      window.location.href = "/login";
      throw new ApiError(401, "Session expired");
    }
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body?.detail || body?.error?.message || res.statusText,
      body?.error?.code
    );
  }

  return res.json();
}

async function requestFormData<T>(path: string, formData: FormData): Promise<T> {
  const token = getSessionToken();
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const res = await fetch(`${getBaseUrl()}${path}`, {
    method: "POST",
    cache: "no-store",
    headers,
    body: formData
  });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      clearAuth();
      window.location.href = "/login";
      throw new ApiError(401, "Session expired");
    }
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail || res.statusText);
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

// Collections

export interface Collection {
  id: string;
  name: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  dimension: number;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export async function listCollections() {
  return request<{ collections: Collection[] }>("/v1/collections");
}

export async function getCollection(name: string) {
  return request<Collection>(`/v1/collections/${encodeURIComponent(name)}`);
}

export interface CreateCollectionBody {
  name: string;
  description?: string;
  embedding_provider?: string;
  embedding_model?: string;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
}

export async function createCollection(body: CreateCollectionBody) {
  return request<Collection>("/v1/collections", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function deleteCollection(name: string) {
  return request<{ status: string }>(`/v1/collections/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
}

// Documents

export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export async function listDocuments(collectionName: string, status?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  return request<{ documents: Document[]; total: number }>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents?${params}`
  );
}

export async function getDocument(collectionName: string, documentId: string) {
  return request<Document>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}`
  );
}

export async function uploadDocument(collectionName: string, file: File, metadata?: Record<string, unknown>) {
  const formData = new FormData();
  formData.append("file", file);
  if (metadata) formData.append("metadata", JSON.stringify(metadata));
  return requestFormData<Document>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents`,
    formData
  );
}

export async function deleteDocument(collectionName: string, documentId: string) {
  return request<{ status: string }>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}`,
    { method: "DELETE" }
  );
}

export async function reprocessDocument(collectionName: string, documentId: string) {
  return request<{ status: string }>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}/reprocess`,
    { method: "POST" }
  );
}

// Query

export interface QueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
}

export async function queryCollection(
  collectionName: string,
  body: { query: string; top_k?: number; filters?: Record<string, unknown>; min_score?: number }
) {
  return request<QueryResponse>(
    `/v1/collections/${encodeURIComponent(collectionName)}/query`,
    { body: JSON.stringify(body), method: "POST" }
  );
}

// Embeddings

export interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

export async function listEmbeddingModels() {
  return request<{ models: EmbeddingModelInfo[] }>("/v1/embeddings/models");
}

// Metrics

export async function getMetrics() {
  const token = getSessionToken();
  const res = await fetch(`${getBaseUrl()}/v1/metrics`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  return res.text();
}

// Auth

export interface AuthResponse {
  token: string;
  user: {
    id: string;
    email: string;
    display_name: string;
    role: string;
    created_at: string;
    updated_at: string;
  };
}

export async function getSetupStatus() {
  return request<{ needs_setup: boolean }>("/v1/auth/setup-status");
}

export async function setupAdmin(body: { email: string; password: string; display_name: string }) {
  return request<AuthResponse>("/v1/auth/setup", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function login(body: { email: string; password: string }) {
  return request<AuthResponse>("/v1/auth/login", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function signup(body: { email: string; password: string; display_name: string; invite_code: string }) {
  return request<AuthResponse>("/v1/auth/signup", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function getMe() {
  return request<{ user: AuthResponse["user"] }>("/v1/auth/me");
}

export async function logout() {
  return request<{ status: string }>("/v1/auth/logout", { method: "POST" });
}

export async function changePassword(body: { current_password: string; new_password: string }) {
  return request<{ status: string }>("/v1/auth/password", {
    body: JSON.stringify(body),
    method: "PUT"
  });
}

// Admin - Users

export interface UserSummary {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export async function listUsers() {
  return request<{ users: UserSummary[] }>("/v1/admin/users");
}

export async function deleteUser(id: string) {
  return request<{ status: string; message: string }>(`/v1/admin/users/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export async function updateUserRole(id: string, role: string) {
  return request<{ status: string }>(`/v1/admin/users/${encodeURIComponent(id)}`, {
    body: JSON.stringify({ role }),
    method: "PATCH"
  });
}

// Admin - Invites

export interface InviteSummary {
  id: string;
  code: string;
  role: string;
  expires_at: string;
  created_at: string;
  used_by: string | null;
  created_by_email: string;
}

export async function createInvite(body: { role?: string; expires_in_hours?: number }) {
  return request<InviteSummary>("/v1/admin/invites", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function listInvites() {
  return request<{ invites: InviteSummary[] }>("/v1/admin/invites");
}

export async function deleteInvite(id: string) {
  return request<{ status: string; message: string }>(`/v1/admin/invites/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

// Admin - API Keys

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
