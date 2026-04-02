# TypeScript SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-dependency, fetch-based TypeScript SDK (`@bigrag/client`) that covers the full bigRAG API and replaces the frontend's hand-rolled `api.ts`.

**Architecture:** Single `BigRAG` class with flat methods wrapping `fetch`. SSE streaming via `ReadableStream` parsing. Universal runtime support (browser, Node 18+, edge). Frontend migrates from standalone functions to SDK client methods.

**Tech Stack:** TypeScript 6, native `fetch`, ESM-only

**Spec:** `docs/superpowers/specs/2026-04-02-typescript-sdk-design.md`

---

### Task 1: Clean up stale artifacts and configure package

**Files:**
- Delete: `sdks/typescript/dist/` (all stale files from old namespaces API)
- Delete: `sdks/typescript/src/index.ts` (3-line stub)
- Modify: `sdks/typescript/package.json`
- Modify: `sdks/typescript/tsconfig.json`

- [ ] **Step 1: Delete stale dist/ directory and add .gitignore**

```bash
rm -rf sdks/typescript/dist/
```

Create `sdks/typescript/.gitignore`:

```
node_modules/
dist/
```

- [ ] **Step 2: Update package.json**

Replace the contents of `sdks/typescript/package.json` with:

```json
{
  "name": "@bigrag/client",
  "version": "0.1.0",
  "description": "TypeScript client for bigRAG — a self-hostable RAG platform",
  "license": "Apache-2.0",
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
  },
  "files": [
    "dist",
    "README.md"
  ],
  "engines": {
    "node": ">=18"
  },
  "scripts": {
    "build": "tsc",
    "prepublishOnly": "tsc"
  },
  "devDependencies": {
    "@types/node": "^25.5.0",
    "typescript": "^6.0.2"
  }
}
```

- [ ] **Step 3: Update tsconfig.json**

Replace the contents of `sdks/typescript/tsconfig.json` with:

```json
{
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "strict": true,
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "esModuleInterop": true,
    "types": ["node"],
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 4: Commit**

```bash
git add sdks/typescript/.gitignore sdks/typescript/package.json sdks/typescript/tsconfig.json
git rm -r --cached sdks/typescript/dist/ 2>/dev/null; true
git rm sdks/typescript/src/index.ts 2>/dev/null; true
git commit -m "chore: clean up stale SDK artifacts and configure package"
```

---

### Task 2: Write error hierarchy

**Files:**
- Create: `sdks/typescript/src/errors.ts`

- [ ] **Step 1: Write errors.ts**

Create `sdks/typescript/src/errors.ts`:

```typescript
export class BigRAGError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BigRAGError";
  }
}

export class APIError extends BigRAGError {
  readonly status: number;
  readonly code: string | undefined;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
  }
}

export class BadRequestError extends APIError {
  constructor(message: string, code?: string) {
    super(400, message, code);
    this.name = "BadRequestError";
  }
}

export class AuthenticationError extends APIError {
  constructor(message: string, code?: string) {
    super(401, message, code);
    this.name = "AuthenticationError";
  }
}

export class NotFoundError extends APIError {
  constructor(message: string, code?: string) {
    super(404, message, code);
    this.name = "NotFoundError";
  }
}

export class RateLimitError extends APIError {
  constructor(message: string, code?: string) {
    super(429, message, code);
    this.name = "RateLimitError";
  }
}

export class InternalServerError extends APIError {
  constructor(message: string, code?: string) {
    super(500, message, code);
    this.name = "InternalServerError";
  }
}

export class APIConnectionError extends BigRAGError {
  constructor(message: string = "Connection error") {
    super(message);
    this.name = "APIConnectionError";
  }
}

export class APITimeoutError extends BigRAGError {
  constructor(message: string = "Request timed out") {
    super(message);
    this.name = "APITimeoutError";
  }
}

const STATUS_MAP: Record<number, new (message: string, code?: string) => APIError> = {
  400: BadRequestError,
  401: AuthenticationError,
  404: NotFoundError,
  429: RateLimitError,
  500: InternalServerError,
};

export function errorForStatus(
  status: number,
  message: string,
  code?: string,
): APIError {
  const Cls = STATUS_MAP[status];
  if (Cls) return new Cls(message, code);
  return new APIError(status, message, code);
}
```

- [ ] **Step 2: Commit**

```bash
git add sdks/typescript/src/errors.ts
git commit -m "feat: add SDK error hierarchy"
```

---

### Task 3: Write type definitions

**Files:**
- Create: `sdks/typescript/src/types.ts`

- [ ] **Step 1: Write types.ts**

Create `sdks/typescript/src/types.ts`. These types mirror the API's Pydantic models and match the interfaces the frontend already uses.

```typescript
// --- Common ---

export interface StatusResponse {
  status: string;
  message?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

// --- Collections ---

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

export interface CollectionListResponse {
  collections: Collection[];
}

export interface CreateCollectionBody {
  name: string;
  description?: string;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_api_key?: string;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
}

export interface UpdateCollectionBody {
  description?: string;
  metadata?: Record<string, unknown>;
}

// --- Documents ---

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

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface DocumentListOptions {
  status?: string;
  limit?: number;
  offset?: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface DocumentChunkListResponse {
  chunks: DocumentChunk[];
  total: number;
}

// --- Query ---

export interface QueryBody {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
}

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

// --- Vectors ---

export interface VectorEntry {
  id: string;
  embedding: number[];
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface UpsertResponse {
  status: string;
  upserted: number;
}

export interface DeleteResponse {
  status: string;
  deleted: number;
}

// --- Auth ---

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface SetupBody {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginBody {
  email: string;
  password: string;
}

export interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}

export interface SetupStatusResponse {
  needs_setup: boolean;
}

export interface MeResponse {
  user: User;
}

// --- Admin ---

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

export interface CreateApiKeyBody {
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

export interface ApiKeyListResponse {
  keys: ApiKeySummary[];
}

// --- Embeddings ---

export interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

export interface EmbeddingModelListResponse {
  models: EmbeddingModelInfo[];
}

// --- SSE ---

export interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  status?: string;
  detail?: Record<string, unknown>;
}

// --- File input ---

export type FileInput =
  | File
  | Blob
  | Buffer
  | Uint8Array
  | { path: string; name?: string };
```

- [ ] **Step 2: Commit**

```bash
git add sdks/typescript/src/types.ts
git commit -m "feat: add SDK type definitions"
```

---

### Task 4: Write SSE stream parser

**Files:**
- Create: `sdks/typescript/src/sse.ts`

- [ ] **Step 1: Write sse.ts**

Create `sdks/typescript/src/sse.ts`. This parses `text/event-stream` from a `fetch` `Response` body using `ReadableStream`, which works in all runtimes (unlike `EventSource`).

```typescript
import type { ProgressEvent } from "./types.js";

export async function* parseSSEStream(
  response: Response,
): AsyncGenerator<ProgressEvent> {
  const body = response.body;
  if (!body) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const json = line.slice(6).trim();
        if (!json) continue;
        try {
          yield JSON.parse(json) as ProgressEvent;
        } catch {
          // skip malformed JSON
        }
      }
    }

    // flush remaining buffer
    if (buffer.startsWith("data: ")) {
      const json = buffer.slice(6).trim();
      if (json) {
        try {
          yield JSON.parse(json) as ProgressEvent;
        } catch {
          // skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add sdks/typescript/src/sse.ts
git commit -m "feat: add SSE stream parser"
```

---

### Task 5: Write the BigRAG client

**Files:**
- Create: `sdks/typescript/src/client.ts`

- [ ] **Step 1: Write client.ts**

Create `sdks/typescript/src/client.ts`:

```typescript
import {
  APIConnectionError,
  APITimeoutError,
  errorForStatus,
} from "./errors.js";
import { parseSSEStream } from "./sse.js";
import type {
  ApiKeyListResponse,
  AuthResponse,
  ChangePasswordBody,
  Collection,
  CollectionListResponse,
  CreateApiKeyBody,
  CreateApiKeyResponse,
  CreateCollectionBody,
  DeleteResponse,
  Document,
  DocumentChunkListResponse,
  DocumentListOptions,
  DocumentListResponse,
  EmbeddingModelListResponse,
  FileInput,
  HealthResponse,
  LoginBody,
  MeResponse,
  ProgressEvent,
  QueryBody,
  QueryResponse,
  SetupBody,
  SetupStatusResponse,
  StatusResponse,
  UpdateCollectionBody,
  UpsertResponse,
  VectorEntry,
} from "./types.js";

const DEFAULT_BASE_URL = "http://localhost:8080";
const DEFAULT_TIMEOUT = 120_000;
const DEFAULT_MAX_RETRIES = 2;
const USER_AGENT = "bigrag-typescript/0.1.0";

export interface BigRAGOptions {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  fetch?: typeof globalThis.fetch;
}

export class BigRAG {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeout: number;
  readonly maxRetries: number;
  private readonly _fetch: typeof globalThis.fetch;

  constructor(options: BigRAGOptions = {}) {
    this.apiKey =
      options.apiKey ??
      (typeof process !== "undefined"
        ? (process.env as Record<string, string | undefined>).BIGRAG_API_KEY ?? ""
        : "");
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this._fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  // ---- Internal request helpers ----

  private _headers(): Record<string, string> {
    const h: Record<string, string> = {
      "User-Agent": USER_AGENT,
    };
    if (this.apiKey) h["Authorization"] = `Bearer ${this.apiKey}`;
    return h;
  }

  private async _request<T>(
    method: string,
    path: string,
    opts?: { json?: unknown; params?: Record<string, string> },
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (opts?.params) {
      const sp = new URLSearchParams(opts.params);
      url += `?${sp}`;
    }

    const headers: Record<string, string> = { ...this._headers() };
    let body: string | undefined;
    if (opts?.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    }

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        await sleep(Math.min(0.5 * 2 ** attempt, 4) * 1000);
      }

      let response: Response;
      try {
        response = await this._fetch(url, {
          method,
          headers,
          body,
          signal: AbortSignal.timeout(this.timeout),
        });
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (lastError.name === "TimeoutError" || lastError.name === "AbortError") {
          if (attempt < this.maxRetries) continue;
          throw new APITimeoutError(lastError.message);
        }
        if (attempt < this.maxRetries) continue;
        throw new APIConnectionError(lastError.message);
      }

      if (response.status >= 500 && attempt < this.maxRetries) {
        lastError = new Error(await response.text().catch(() => "Server error"));
        continue;
      }

      if (response.status === 429 && attempt < this.maxRetries) {
        lastError = new Error("Rate limited");
        continue;
      }

      if (response.status >= 400) {
        let errBody: { detail?: string; error?: { message?: string; code?: string }; message?: string };
        try {
          errBody = await response.json();
        } catch {
          errBody = {};
        }
        const message =
          errBody.detail ??
          errBody.error?.message ??
          errBody.message ??
          response.statusText;
        const code = errBody.error?.code;
        throw errorForStatus(response.status, message, code);
      }

      if (response.status === 204) return { status: "ok" } as T;

      const text = await response.text();
      if (!text) return { status: "ok" } as T;
      return JSON.parse(text) as T;
    }

    throw new APIConnectionError(lastError?.message ?? "Request failed");
  }

  private async _requestFormData<T>(
    path: string,
    formData: FormData,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = { ...this._headers() };
    // Do not set Content-Type — fetch sets it with the multipart boundary

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        await sleep(Math.min(0.5 * 2 ** attempt, 4) * 1000);
      }

      let response: Response;
      try {
        response = await this._fetch(url, {
          method: "POST",
          headers,
          body: formData,
          signal: AbortSignal.timeout(this.timeout),
        });
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (lastError.name === "TimeoutError" || lastError.name === "AbortError") {
          if (attempt < this.maxRetries) continue;
          throw new APITimeoutError(lastError.message);
        }
        if (attempt < this.maxRetries) continue;
        throw new APIConnectionError(lastError.message);
      }

      if (response.status >= 500 && attempt < this.maxRetries) {
        lastError = new Error(await response.text().catch(() => "Server error"));
        continue;
      }

      if (response.status === 429 && attempt < this.maxRetries) {
        lastError = new Error("Rate limited");
        continue;
      }

      if (response.status >= 400) {
        let errBody: { detail?: string; error?: { message?: string; code?: string }; message?: string };
        try {
          errBody = await response.json();
        } catch {
          errBody = {};
        }
        const message =
          errBody.detail ??
          errBody.error?.message ??
          errBody.message ??
          response.statusText;
        throw errorForStatus(response.status, message);
      }

      return (await response.json()) as T;
    }

    throw new APIConnectionError(lastError?.message ?? "Request failed");
  }

  private async _requestText(
    path: string,
  ): Promise<string> {
    const url = `${this.baseUrl}${path}`;
    const response = await this._fetch(url, {
      method: "GET",
      headers: this._headers(),
      signal: AbortSignal.timeout(this.timeout),
    });
    if (!response.ok) {
      throw errorForStatus(response.status, response.statusText);
    }
    return response.text();
  }

  // ---- Helpers for file input normalization ----

  private async _buildUploadForm(
    file: FileInput,
    metadata?: Record<string, unknown>,
  ): Promise<FormData> {
    const form = new FormData();

    if (file instanceof Blob) {
      // File extends Blob, so this handles both File and Blob
      const name = file instanceof File ? file.name : "document";
      form.append("file", file, name);
    } else if (file instanceof Uint8Array || (typeof Buffer !== "undefined" && Buffer.isBuffer(file))) {
      form.append("file", new Blob([file]), "document");
    } else if (typeof file === "object" && "path" in file) {
      // Node.js file path — dynamic import to avoid breaking browser bundles
      const { readFile } = await import("node:fs/promises");
      const { basename } = await import("node:path");
      const data = await readFile(file.path);
      const name = file.name ?? basename(file.path);
      form.append("file", new Blob([data]), name);
    }

    if (metadata) {
      form.append("metadata", JSON.stringify(metadata));
    }

    return form;
  }

  // ---- Health ----

  health(): Promise<HealthResponse> {
    return this._request("GET", "/health");
  }

  // ---- Collections ----

  listCollections(): Promise<CollectionListResponse> {
    return this._request("GET", "/v1/collections");
  }

  createCollection(body: CreateCollectionBody): Promise<Collection> {
    return this._request("POST", "/v1/collections", { json: body });
  }

  getCollection(name: string): Promise<Collection> {
    return this._request("GET", `/v1/collections/${encodeURIComponent(name)}`);
  }

  updateCollection(
    name: string,
    body: UpdateCollectionBody,
  ): Promise<Collection> {
    return this._request("PUT", `/v1/collections/${encodeURIComponent(name)}`, {
      json: body,
    });
  }

  deleteCollection(name: string): Promise<StatusResponse> {
    return this._request("DELETE", `/v1/collections/${encodeURIComponent(name)}`);
  }

  // ---- Documents ----

  async uploadDocument(
    collection: string,
    file: FileInput,
    metadata?: Record<string, unknown>,
  ): Promise<Document> {
    const form = await this._buildUploadForm(file, metadata);
    return this._requestFormData(
      `/v1/collections/${encodeURIComponent(collection)}/documents`,
      form,
    );
  }

  listDocuments(
    collection: string,
    options?: DocumentListOptions,
  ): Promise<DocumentListResponse> {
    const params: Record<string, string> = {};
    if (options?.status) params.status = options.status;
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents`,
      { params },
    );
  }

  getDocument(collection: string, documentId: string): Promise<Document> {
    return this._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  deleteDocument(
    collection: string,
    documentId: string,
  ): Promise<StatusResponse> {
    return this._request(
      "DELETE",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  reprocessDocument(
    collection: string,
    documentId: string,
  ): Promise<StatusResponse> {
    return this._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/reprocess`,
    );
  }

  getDocumentChunks(
    collection: string,
    documentId: string,
  ): Promise<DocumentChunkListResponse> {
    return this._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/chunks`,
    );
  }

  getDocumentFileUrl(collection: string, documentId: string): string {
    const path = `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/file`;
    if (this.apiKey) {
      return `${this.baseUrl}${path}?token=${encodeURIComponent(this.apiKey)}`;
    }
    return `${this.baseUrl}${path}`;
  }

  async *streamDocumentProgress(
    collection: string,
    documentId: string,
  ): AsyncGenerator<ProgressEvent> {
    const path = `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/progress`;
    const tokenParam = this.apiKey
      ? `?token=${encodeURIComponent(this.apiKey)}`
      : "";
    const url = `${this.baseUrl}${path}${tokenParam}`;

    const response = await this._fetch(url, {
      method: "GET",
      headers: { "User-Agent": USER_AGENT },
    });

    if (!response.ok) {
      throw errorForStatus(response.status, response.statusText);
    }

    yield* parseSSEStream(response);
  }

  // ---- Query ----

  query(collection: string, body: QueryBody): Promise<QueryResponse> {
    return this._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/query`,
      { json: body },
    );
  }

  // ---- Vectors ----

  upsertVectors(
    collection: string,
    vectors: VectorEntry[],
  ): Promise<UpsertResponse> {
    return this._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/vectors/upsert`,
      { json: { vectors } },
    );
  }

  deleteVectors(
    collection: string,
    ids: string[],
  ): Promise<DeleteResponse> {
    return this._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/vectors/delete`,
      { json: { ids } },
    );
  }

  // ---- Embeddings ----

  listEmbeddingModels(): Promise<EmbeddingModelListResponse> {
    return this._request("GET", "/v1/embeddings/models");
  }

  // ---- Metrics ----

  getMetrics(): Promise<string> {
    return this._requestText("/v1/metrics");
  }

  // ---- Auth ----

  getSetupStatus(): Promise<SetupStatusResponse> {
    return this._request("GET", "/v1/auth/setup-status");
  }

  setup(body: SetupBody): Promise<AuthResponse> {
    return this._request("POST", "/v1/auth/setup", { json: body });
  }

  login(body: LoginBody): Promise<AuthResponse> {
    return this._request("POST", "/v1/auth/login", { json: body });
  }

  logout(): Promise<StatusResponse> {
    return this._request("POST", "/v1/auth/logout");
  }

  getMe(): Promise<MeResponse> {
    return this._request("GET", "/v1/auth/me");
  }

  changePassword(body: ChangePasswordBody): Promise<StatusResponse> {
    return this._request("PUT", "/v1/auth/password", { json: body });
  }

  // ---- Admin ----

  createApiKey(body: CreateApiKeyBody): Promise<CreateApiKeyResponse> {
    return this._request("POST", "/v1/admin/api-keys", { json: body });
  }

  listApiKeys(): Promise<ApiKeyListResponse> {
    return this._request("GET", "/v1/admin/api-keys");
  }

  revokeApiKey(id: string): Promise<StatusResponse> {
    return this._request(
      "DELETE",
      `/v1/admin/api-keys/${encodeURIComponent(id)}`,
    );
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
```

- [ ] **Step 2: Commit**

```bash
git add sdks/typescript/src/client.ts
git commit -m "feat: add BigRAG client"
```

---

### Task 6: Write index, build, and verify

**Files:**
- Create: `sdks/typescript/src/index.ts`

- [ ] **Step 1: Write index.ts**

Create `sdks/typescript/src/index.ts`:

```typescript
export { BigRAG } from "./client.js";
export type { BigRAGOptions } from "./client.js";
export * from "./types.js";
export * from "./errors.js";
```

- [ ] **Step 2: Install deps and build**

```bash
cd sdks/typescript && npm install && npm run build
```

Expected: Clean compilation, `dist/` populated with `.js`, `.d.ts` files.

- [ ] **Step 3: Verify dist/ output**

```bash
ls sdks/typescript/dist/
```

Expected files: `index.js`, `index.d.ts`, `client.js`, `client.d.ts`, `types.js`, `types.d.ts`, `errors.js`, `errors.d.ts`, `sse.js`, `sse.d.ts`.

- [ ] **Step 4: Commit**

```bash
git add sdks/typescript/src/index.ts
git commit -m "feat: add SDK index and verify build"
```

---

### Task 7: Update README

**Files:**
- Modify: `sdks/typescript/README.md`

- [ ] **Step 1: Write README.md**

Replace the contents of `sdks/typescript/README.md`:

```markdown
# @bigrag/client

TypeScript client for [bigRAG](https://github.com/yoginth/bigrag) — a self-hostable RAG platform.

Zero dependencies. Works in Node.js 18+, browsers, Deno, Bun, and edge runtimes.

## Installation

```bash
npm install @bigrag/client
```

## Quick Start

```typescript
import { BigRAG } from "@bigrag/client";

const client = new BigRAG({
  apiKey: "your-api-key",
  baseUrl: "http://localhost:8080",
});

// List collections
const { collections } = await client.listCollections();

// Upload a document
const doc = await client.uploadDocument("my_collection", file);

// Query
const results = await client.query("my_collection", {
  query: "What is RAG?",
  top_k: 5,
});

// Stream document processing progress
for await (const event of client.streamDocumentProgress("my_collection", doc.id)) {
  console.log(event.step, event.progress);
  if (event.status === "complete") break;
}
```

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `apiKey` | `BIGRAG_API_KEY` env var | API key or session token |
| `baseUrl` | `http://localhost:8080` | bigRAG server URL |
| `timeout` | `120000` | Request timeout in milliseconds |
| `maxRetries` | `2` | Max retries on 5xx, 429, and network errors |
| `fetch` | `globalThis.fetch` | Custom fetch implementation |

## Error Handling

```typescript
import { BigRAG, AuthenticationError, NotFoundError } from "@bigrag/client";

try {
  await client.getCollection("missing");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.log("Collection not found");
  } else if (err instanceof AuthenticationError) {
    console.log("Invalid credentials");
  }
}
```

## License

Apache-2.0
```

- [ ] **Step 2: Commit**

```bash
git add sdks/typescript/README.md
git commit -m "docs: update SDK README"
```

---

### Task 8: Wire the frontend to use the SDK

**Files:**
- Modify: `ui/package.json` (add `@bigrag/client` dependency)
- Create: `ui/src/lib/client.ts` (thin helper that creates BigRAG instances)
- Modify: `ui/src/lib/queries.ts`
- Modify: `ui/src/components/auth-guard.tsx`
- Modify: `ui/src/components/sidebar.tsx`
- Modify: `ui/src/app/login/page.tsx`
- Modify: `ui/src/app/setup/page.tsx`
- Modify: `ui/src/app/(dashboard)/collections/page.tsx`
- Modify: `ui/src/app/(dashboard)/collections/[name]/page.tsx`
- Modify: `ui/src/app/(dashboard)/collections/[name]/documents/[documentId]/page.tsx`
- Modify: `ui/src/app/(dashboard)/api-keys/page.tsx`
- Modify: `ui/src/app/(dashboard)/settings/page.tsx`
- Modify: `ui/src/app/(dashboard)/query/page.tsx`
- Delete: `ui/src/lib/api.ts`

- [ ] **Step 1: Add SDK dependency to frontend**

In `ui/package.json`, add to `dependencies`:

```json
"@bigrag/client": "file:../../sdks/typescript"
```

Then install:

```bash
cd ui && npm install
```

- [ ] **Step 2: Create ui/src/lib/client.ts**

Create `ui/src/lib/client.ts`:

```typescript
import { BigRAG } from "@bigrag/client";
import { getBaseUrl, getSessionToken } from "./auth-store";

export const getClient = () =>
  new BigRAG({
    apiKey: getSessionToken(),
    baseUrl: getBaseUrl(),
  });
```

- [ ] **Step 3: Migrate ui/src/lib/queries.ts**

Replace `ui/src/lib/queries.ts` with:

```typescript
import { queryOptions } from "@tanstack/react-query";
import { getClient } from "./client";

export const healthQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().health(),
    queryKey: ["health"]
  });

export const collectionsQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().listCollections(),
    queryKey: ["collections"]
  });

export const collectionQueryOptions = (name: string) =>
  queryOptions({
    queryFn: () => getClient().getCollection(name),
    queryKey: ["collection", name]
  });

export const documentsQueryOptions = (
  collectionName: string,
  status?: string
) =>
  queryOptions({
    queryFn: () => getClient().listDocuments(collectionName, status ? { status } : undefined),
    queryKey: ["documents", collectionName, status]
  });

export const embeddingModelsQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().listEmbeddingModels(),
    queryKey: ["embedding-models"]
  });

export const metricsQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().getMetrics(),
    queryKey: ["metrics"],
    refetchInterval: 10_000
  });
```

- [ ] **Step 4: Migrate ui/src/components/auth-guard.tsx**

Change line 5 from:
```typescript
import { ApiError, getMe, getSetupStatus } from "@/lib/api";
```
to:
```typescript
import { APIError } from "@bigrag/client";
import { getClient } from "@/lib/client";
```

Change line 24 (`const { needs_setup } = await getSetupStatus();`) to:
```typescript
      const { needs_setup } = await getClient().getSetupStatus();
```

Change line 33 (`if (err instanceof ApiError && err.status >= 500) {`) to:
```typescript
      if (err instanceof APIError && err.status >= 500) {
```

Change line 60 (`const { user } = await getMe();`) to:
```typescript
      const { user } = await getClient().getMe();
```

- [ ] **Step 5: Migrate ui/src/components/sidebar.tsx**

Change line 15 from:
```typescript
import { logout } from "@/lib/api";
```
to:
```typescript
import { getClient } from "@/lib/client";
```

Change line 34 (`await logout();`) to:
```typescript
      await getClient().logout();
```

- [ ] **Step 6: Migrate ui/src/app/login/page.tsx**

Change line 6 from:
```typescript
import { login } from "@/lib/api";
```
to:
```typescript
import { getClient } from "@/lib/client";
```

Change line 22 (`const res = await login({ email, password });`) to:
```typescript
      const res = await getClient().login({ email, password });
```

- [ ] **Step 7: Migrate ui/src/app/setup/page.tsx**

Change line 6 from:
```typescript
import { setupAdmin } from "@/lib/api";
```
to:
```typescript
import { getClient } from "@/lib/client";
```

Change line 22 (`const res = await setupAdmin({ display_name: name, email, password });`) to:
```typescript
      const res = await getClient().setup({ display_name: name, email, password });
```

- [ ] **Step 8: Migrate ui/src/app/(dashboard)/collections/page.tsx**

Change line 7 from:
```typescript
import { createCollection, deleteCollection } from "@/lib/api";
```
to:
```typescript
import { getClient } from "@/lib/client";
```

Change the `createMutation` `mutationFn` (line 33-48) — replace:
```typescript
    mutationFn: () =>
      createCollection({
```
with:
```typescript
    mutationFn: () =>
      getClient().createCollection({
```

Change the `deleteMutation` `mutationFn` (line 62) — replace:
```typescript
    mutationFn: deleteCollection,
```
with:
```typescript
    mutationFn: (name: string) => getClient().deleteCollection(name),
```

- [ ] **Step 9: Migrate ui/src/app/(dashboard)/collections/[name]/page.tsx**

Change lines 18-24 from:
```typescript
import {
  deleteDocument,
  getDocumentFileUrl,
  reprocessDocument,
  uploadDocument
} from "@/lib/api";
import { getBaseUrl, getSessionToken } from "@/lib/auth-store";
```
to:
```typescript
import type { ProgressEvent } from "@bigrag/client";
import { getClient } from "@/lib/client";
import { getBaseUrl, getSessionToken } from "@/lib/auth-store";
```

Remove the local `ProgressEvent` interface (lines 43-49) since it's now imported from `@bigrag/client`. Rename usage of the local type — the page defines `UploadProgress.events` as `ProgressEvent[]`. Since the SDK's `ProgressEvent` has `step`, `message`, `progress`, `status?`, `detail?` — and the local one has `step`, `message`, `progress`, `time`, `detail?` — they are not identical. The local `ProgressEvent` includes a `time` field that's added client-side. Keep a local `ProgressEventWithTime` type:

Replace lines 43-49:
```typescript
interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  time: number;
  detail?: Record<string, unknown>;
}
```
with:
```typescript
interface ProgressEventWithTime {
  step: string;
  message: string;
  progress: number;
  time: number;
  detail?: Record<string, unknown>;
}
```

And update the `UploadProgress` interface (line 39) to use `ProgressEventWithTime`:
```typescript
  events: ProgressEventWithTime[];
```

Update the event variable type (line 207) and all constructions of `ProgressEventWithTime` (lines 207, 302, 352, 370) to use the new name.

Change the `deleteMutation` (line 181):
```typescript
    mutationFn: (docId: string) => deleteDocument(name, docId),
```
to:
```typescript
    mutationFn: (docId: string) => getClient().deleteDocument(name, docId),
```

Change the `reprocessMutation` (line 189):
```typescript
    mutationFn: (docId: string) => reprocessDocument(name, docId),
```
to:
```typescript
    mutationFn: (docId: string) => getClient().reprocessDocument(name, docId),
```

Change `uploadDocument` call (line 343):
```typescript
          const doc = await uploadDocument(name, file);
```
to:
```typescript
          const doc = await getClient().uploadDocument(name, file);
```

Change `getDocumentFileUrl` call (line 623):
```typescript
                            href={getDocumentFileUrl(name, doc.id)}
```
to:
```typescript
                            href={getClient().getDocumentFileUrl(name, doc.id)}
```

- [ ] **Step 10: Migrate ui/src/app/(dashboard)/collections/[name]/documents/[documentId]/page.tsx**

Change lines 14-20 from:
```typescript
import {
  type Document,
  getDocument,
  getDocumentChunks,
  getDocumentFileUrl
} from "@/lib/api";
```
to:
```typescript
import type { Document } from "@bigrag/client";
import { getClient } from "@/lib/client";
```

Change `getDocument` call (line 31):
```typescript
    queryFn: () => getDocument(name, documentId),
```
to:
```typescript
    queryFn: () => getClient().getDocument(name, documentId),
```

Change `getDocumentChunks` call (line 37):
```typescript
    queryFn: () => getDocumentChunks(name, documentId),
```
to:
```typescript
    queryFn: () => getClient().getDocumentChunks(name, documentId),
```

Change both `getDocumentFileUrl` calls (line 73 and line 207 area) to `getClient().getDocumentFileUrl(name, doc.id)`.

- [ ] **Step 11: Migrate ui/src/app/(dashboard)/api-keys/page.tsx**

Change lines 5-10 from:
```typescript
import {
  type CreateApiKeyRequest,
  createApiKey,
  listApiKeys,
  revokeApiKey
} from "@/lib/api";
```
to:
```typescript
import type { CreateApiKeyBody } from "@bigrag/client";
import { getClient } from "@/lib/client";
```

Change line 13 (`queryFn: () => listApiKeys(),`):
```typescript
  queryFn: () => getClient().listApiKeys(),
```

Change line 31 — the mutation function type and call:
```typescript
    mutationFn: (body: CreateApiKeyRequest) => createApiKey(body),
```
to:
```typescript
    mutationFn: (body: CreateApiKeyBody) => getClient().createApiKey(body),
```

Change line 44 (`mutationFn: (id: string) => revokeApiKey(id),`):
```typescript
    mutationFn: (id: string) => getClient().revokeApiKey(id),
```

- [ ] **Step 12: Migrate ui/src/app/(dashboard)/settings/page.tsx**

Change line 5 from:
```typescript
import { changePassword } from "@/lib/api";
```
to:
```typescript
import { getClient } from "@/lib/client";
```

Change the `passwordMutation` `mutationFn` (lines 21-24):
```typescript
    mutationFn: () =>
      changePassword({
        current_password: currentPassword,
        new_password: newPassword
      }),
```
to:
```typescript
    mutationFn: () =>
      getClient().changePassword({
        current_password: currentPassword,
        new_password: newPassword
      }),
```

- [ ] **Step 13: Migrate ui/src/app/(dashboard)/query/page.tsx**

Change lines 6-7 from:
```typescript
import type { QueryResponse } from "@/lib/api";
import { queryCollection } from "@/lib/api";
```
to:
```typescript
import type { QueryResponse } from "@bigrag/client";
import { getClient } from "@/lib/client";
```

Change the `queryMutation` `mutationFn` (lines 19-24):
```typescript
    mutationFn: () =>
      queryCollection(selectedCollection, {
```
to:
```typescript
    mutationFn: () =>
      getClient().query(selectedCollection, {
```

- [ ] **Step 14: Delete ui/src/lib/api.ts**

```bash
rm ui/src/lib/api.ts
```

- [ ] **Step 15: Build the frontend**

```bash
cd ui && npm run build
```

Expected: Clean build with no errors.

- [ ] **Step 16: Commit**

```bash
git add ui/ sdks/typescript/
git commit -m "feat: migrate frontend to @bigrag/client SDK"
```

