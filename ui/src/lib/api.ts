import { clearAuth, getBaseUrl, getSessionToken } from "./auth-store";

const request = async <T>(
  path: string,
  options: RequestInit = {}
): Promise<T> => {
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
    if (
      res.status === 401 &&
      typeof window !== "undefined" &&
      !path.startsWith("/v1/auth/")
    ) {
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
};

const requestFormData = async <T>(
  path: string,
  formData: FormData
): Promise<T> => {
  const token = getSessionToken();
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  const res = await fetch(`${getBaseUrl()}${path}`, {
    body: formData,
    cache: "no-store",
    headers,
    method: "POST"
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
};

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

export const getHealth = () =>
  request<{ status: string; version: string }>("/health");

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
  has_api_key: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export const listCollections = () =>
  request<{ collections: Collection[] }>("/v1/collections");

export const getCollection = (name: string) =>
  request<Collection>(`/v1/collections/${encodeURIComponent(name)}`);

export interface CreateCollectionBody {
  name: string;
  description?: string;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_api_key?: string;
  embedding_base_url?: string;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
}

export const createCollection = (body: CreateCollectionBody) =>
  request<Collection>("/v1/collections", {
    body: JSON.stringify(body),
    method: "POST"
  });

export const updateCollection = (
  name: string,
  body: { description?: string; metadata?: Record<string, unknown> }
) =>
  request<Collection>(`/v1/collections/${encodeURIComponent(name)}`, {
    body: JSON.stringify(body),
    method: "PUT"
  });

export const deleteCollection = (name: string) =>
  request<{ status: string }>(
    `/v1/collections/${encodeURIComponent(name)}`,
    { method: "DELETE" }
  );

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

export const getDocument = (collectionName: string, documentId: string) =>
  request<Document>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}`
  );

export const listDocuments = (collectionName: string, status?: string) => {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  return request<{ documents: Document[]; total: number }>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents?${params}`
  );
};

export const uploadDocument = (
  collectionName: string,
  file: File,
  metadata?: Record<string, unknown>
) => {
  const formData = new FormData();
  formData.append("file", file);
  if (metadata) formData.append("metadata", JSON.stringify(metadata));
  return requestFormData<Document>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents`,
    formData
  );
};

export const deleteDocument = (collectionName: string, documentId: string) =>
  request<{ status: string }>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}`,
    { method: "DELETE" }
  );

export const getDocumentFileUrl = (
  collectionName: string,
  documentId: string
): string => {
  const token = getSessionToken();
  return `${getBaseUrl()}/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}/file?token=${encodeURIComponent(token)}`;
};

export const reprocessDocument = (
  collectionName: string,
  documentId: string
) =>
  request<{ status: string }>(
    `/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}/reprocess`,
    { method: "POST" }
  );

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

export const queryCollection = (
  collectionName: string,
  body: {
    query: string;
    top_k?: number;
    filters?: Record<string, unknown>;
    min_score?: number;
  }
) =>
  request<QueryResponse>(
    `/v1/collections/${encodeURIComponent(collectionName)}/query`,
    { body: JSON.stringify(body), method: "POST" }
  );

// Embeddings

export interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

export const listEmbeddingModels = () =>
  request<{ models: EmbeddingModelInfo[] }>("/v1/embeddings/models");

// Metrics

export const getMetrics = async () => {
  const token = getSessionToken();
  const res = await fetch(`${getBaseUrl()}/v1/metrics`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  return res.text();
};

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

export const getSetupStatus = () =>
  request<{ needs_setup: boolean }>("/v1/auth/setup-status");

export const setupAdmin = (body: {
  email: string;
  password: string;
  display_name: string;
}) =>
  request<AuthResponse>("/v1/auth/setup", {
    body: JSON.stringify(body),
    method: "POST"
  });

export const login = (body: { email: string; password: string }) =>
  request<AuthResponse>("/v1/auth/login", {
    body: JSON.stringify(body),
    method: "POST"
  });

export const signup = (body: {
  email: string;
  password: string;
  display_name: string;
  invite_code: string;
}) =>
  request<AuthResponse>("/v1/auth/signup", {
    body: JSON.stringify(body),
    method: "POST"
  });

export const getMe = () =>
  request<{ user: AuthResponse["user"] }>("/v1/auth/me");

export const logout = () =>
  request<{ status: string }>("/v1/auth/logout", { method: "POST" });

export const changePassword = (body: {
  current_password: string;
  new_password: string;
}) =>
  request<{ status: string }>("/v1/auth/password", {
    body: JSON.stringify(body),
    method: "PUT"
  });

// Admin - Users

export interface UserSummary {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export const listUsers = () =>
  request<{ users: UserSummary[] }>("/v1/admin/users");

export const deleteUser = (id: string) =>
  request<{ status: string; message: string }>(
    `/v1/admin/users/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );

export const updateUserRole = (id: string, role: string) =>
  request<{ status: string }>(
    `/v1/admin/users/${encodeURIComponent(id)}`,
    {
      body: JSON.stringify({ role }),
      method: "PATCH"
    }
  );

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

export const createInvite = (body: {
  role?: string;
  expires_in_hours?: number;
}) =>
  request<InviteSummary>("/v1/admin/invites", {
    body: JSON.stringify(body),
    method: "POST"
  });

export const listInvites = () =>
  request<{ invites: InviteSummary[] }>("/v1/admin/invites");

export const deleteInvite = (id: string) =>
  request<{ status: string; message: string }>(
    `/v1/admin/invites/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );

// Admin - API Keys

export interface ApiKeyPermissions {
  collections: string[];
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
  collections?: string[];
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

export const createApiKey = (body: CreateApiKeyRequest) =>
  request<CreateApiKeyResponse>("/v1/admin/api-keys", {
    body: JSON.stringify(body),
    method: "POST"
  });

export const listApiKeys = () =>
  request<{ keys: ApiKeySummary[] }>("/v1/admin/api-keys");

export const revokeApiKey = (id: string) =>
  request<{ status: string; message: string }>(
    `/v1/admin/api-keys/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );
