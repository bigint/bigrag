# TypeScript SDK Design Spec

## Overview

Rewrite `@bigrag/client` as a zero-dependency, fetch-based TypeScript SDK that covers the full bigRAG API. The SDK serves two audiences: external consumers (AI apps, gateways, server-side scripts) and the bigRAG admin frontend (Next.js 16). It replaces `ui/src/lib/api.ts` as the single source of truth for types and API surface.

## Package structure

```
sdks/typescript/
├── src/
│   ├── index.ts          # Public exports
│   ├── client.ts         # BigRAG class
│   ├── types.ts          # All request/response interfaces
│   ├── errors.ts         # Error hierarchy
│   └── sse.ts            # SSE stream parser (fetch-based)
├── package.json
├── tsconfig.json
└── README.md
```

## Package config

ESM-only. Zero runtime dependencies.

```json
{
  "name": "@bigrag/client",
  "version": "0.1.0",
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
  },
  "files": ["dist", "README.md"],
  "engines": { "node": ">=18" },
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

`tsconfig.json`: `target: ES2022`, `module: Node16`, `moduleResolution: Node16`, `strict: true`, `declaration: true`.

## Client API

Single `BigRAG` class with flat methods (no sub-resource nesting).

### Constructor

```typescript
class BigRAG {
  constructor(options?: {
    apiKey?: string;      // falls back to BIGRAG_API_KEY env var
    baseUrl?: string;     // defaults to http://localhost:8080
    timeout?: number;     // ms, defaults to 120_000
    maxRetries?: number;  // defaults to 2
    fetch?: typeof fetch; // custom fetch for testing/edge runtimes
  })
}
```

### Methods

| Method | HTTP | Path |
|--------|------|------|
| `health()` | GET | `/health` |
| `listCollections()` | GET | `/v1/collections` |
| `createCollection(body)` | POST | `/v1/collections` |
| `getCollection(name)` | GET | `/v1/collections/{name}` |
| `updateCollection(name, body)` | PUT | `/v1/collections/{name}` |
| `deleteCollection(name)` | DELETE | `/v1/collections/{name}` |
| `uploadDocument(collection, file, metadata?)` | POST | `/v1/collections/{name}/documents` |
| `listDocuments(collection, options?)` | GET | `/v1/collections/{name}/documents` |
| `getDocument(collection, documentId)` | GET | `/v1/collections/{name}/documents/{id}` |
| `deleteDocument(collection, documentId)` | DELETE | `/v1/collections/{name}/documents/{id}` |
| `reprocessDocument(collection, documentId)` | POST | `/v1/collections/{name}/documents/{id}/reprocess` |
| `getDocumentChunks(collection, documentId)` | GET | `/v1/collections/{name}/documents/{id}/chunks` |
| `getDocumentFileUrl(collection, documentId)` | — | Returns URL string with auth token as query param |
| `streamDocumentProgress(collection, documentId)` | GET (SSE) | `/v1/collections/{name}/documents/{id}/progress` |
| `query(collection, body)` | POST | `/v1/collections/{name}/query` |
| `upsertVectors(collection, vectors)` | POST | `/v1/collections/{name}/vectors/upsert` |
| `deleteVectors(collection, ids)` | POST | `/v1/collections/{name}/vectors/delete` |
| `listEmbeddingModels()` | GET | `/v1/embeddings/models` |
| `getMetrics()` | GET | `/v1/metrics` (returns `string`, not JSON — Prometheus format) |
| `getSetupStatus()` | GET | `/v1/auth/setup-status` |
| `setup(body)` | POST | `/v1/auth/setup` |
| `login(body)` | POST | `/v1/auth/login` |
| `logout()` | POST | `/v1/auth/logout` |
| `getMe()` | GET | `/v1/auth/me` |
| `changePassword(body)` | PUT | `/v1/auth/password` |
| `createApiKey(body)` | POST | `/v1/admin/api-keys` |
| `listApiKeys()` | GET | `/v1/admin/api-keys` |
| `revokeApiKey(id)` | DELETE | `/v1/admin/api-keys/{id}` |

### File uploads

`FileInput` type for the `uploadDocument` method:

```typescript
type FileInput =
  | File                                    // browser
  | Blob                                    // browser/node
  | Buffer                                  // node
  | Uint8Array                              // universal
  | { path: string; name?: string }         // node (reads from filesystem)
```

Internally, all inputs are normalized into a `FormData` body. For `{ path: string }`, the SDK uses `fs.readFile` dynamically imported so the module still loads in browsers (the code path is never hit there).

### SSE streaming

`streamDocumentProgress()` returns `AsyncIterable<ProgressEvent>`. Uses `fetch` + `ReadableStream` line-by-line parsing instead of `EventSource` for portability.

```typescript
interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  status?: string;
  detail?: Record<string, unknown>;
}
```

Auth token is passed as a `?token=` query parameter (same pattern the frontend already uses for SSE).

## Types

All types mirror the API's Pydantic models.

### Collection types

```typescript
interface Collection {
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

interface CollectionListResponse {
  collections: Collection[];
}

interface CreateCollectionBody {
  name: string;
  description?: string;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_api_key?: string;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
}

interface UpdateCollectionBody {
  description?: string;
  metadata?: Record<string, unknown>;
}
```

### Document types

```typescript
interface Document {
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

interface DocumentListResponse {
  documents: Document[];
  total: number;
}

interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  metadata: Record<string, unknown>;
}

interface DocumentChunkListResponse {
  chunks: DocumentChunk[];
  total: number;
}
```

### Query types

```typescript
interface QueryBody {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
}

interface QueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  metadata: Record<string, unknown>;
}

interface QueryResponse {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
}
```

### Vector types

```typescript
interface VectorEntry {
  id: string;
  embedding: number[];
  text?: string;
  metadata?: Record<string, unknown>;
}

interface UpsertResponse {
  status: string;
  upserted: number;
}

interface DeleteResponse {
  status: string;
  deleted: number;
}
```

### Auth types

```typescript
interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

interface AuthResponse {
  token: string;
  user: User;
}

interface SetupBody {
  email: string;
  password: string;
  display_name: string;
}

interface LoginBody {
  email: string;
  password: string;
}

interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}

interface SetupStatusResponse {
  needs_setup: boolean;
}

interface MeResponse {
  user: User;
}
```

### Admin types

```typescript
interface ApiKeyPermissions {
  collections: string[];
  operations: string[];
  admin: boolean;
}

interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  permissions: ApiKeyPermissions;
  created_at: string;
  last_used_at?: string;
  expires_at?: string;
}

interface CreateApiKeyBody {
  name: string;
  collections?: string[];
  operations?: string[];
  admin?: boolean;
  expires_at?: string;
}

interface CreateApiKeyResponse {
  key: string;
  id: string;
  name: string;
  prefix: string;
  permissions: ApiKeyPermissions;
  created_at: string;
  expires_at?: string;
}

interface ApiKeyListResponse {
  keys: ApiKeySummary[];
}
```

### Common types

```typescript
interface StatusResponse {
  status: string;
  message?: string;
}

interface HealthResponse {
  status: string;
  version: string;
}

interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

interface EmbeddingModelListResponse {
  models: EmbeddingModelInfo[];
}
```

## Error hierarchy

```typescript
class BigRAGError extends Error {
  message: string;
}

class APIError extends BigRAGError {
  status: number;
  code?: string;
}

class BadRequestError extends APIError {}      // 400
class AuthenticationError extends APIError {}   // 401
class NotFoundError extends APIError {}         // 404
class RateLimitError extends APIError {}        // 429
class InternalServerError extends APIError {}   // 500
class APIConnectionError extends BigRAGError {} // network failures
class APITimeoutError extends BigRAGError {}    // timeout
```

`errorForStatus(status, message, code?)` factory maps status codes to the right subclass.

## Retry logic

- Retries on: 5xx, 429, network errors, timeouts
- Backoff: `min(0.5 * 2^attempt, 4)` seconds
- `maxRetries` defaults to 2 (3 total attempts)
- No retry on 4xx (except 429)
- Matches the Python SDK behavior exactly

## Frontend integration

### SDK wiring

The frontend references the SDK locally:

```json
// ui/package.json
{ "dependencies": { "@bigrag/client": "file:../../sdks/typescript" } }
```

A thin `ui/src/lib/client.ts` creates instances:

```typescript
import { BigRAG } from "@bigrag/client";
import { getBaseUrl, getSessionToken } from "./auth-store";

export const getClient = () =>
  new BigRAG({ apiKey: getSessionToken(), baseUrl: getBaseUrl() });
```

### What gets deleted

`ui/src/lib/api.ts` is deleted entirely. All type and function imports switch to `@bigrag/client`.

### What stays in the frontend

- `ui/src/lib/auth-store.ts` — localStorage token management (UI concern)
- 401 redirect logic — handled in components or a wrapper, not in the SDK. The SDK throws `AuthenticationError`; the frontend catches it and redirects.

### Import changes

All files importing from `@/lib/api` switch to importing types from `@bigrag/client` and functions via `getClient()`.

## Exports

`src/index.ts` re-exports everything public:

```typescript
export { BigRAG } from "./client.js";
export * from "./types.js";
export * from "./errors.js";
```

The SSE module is internal — not exported.
