import {
  APIConnectionError,
  APITimeoutError,
  errorForStatus,
} from "./errors.js";
import { parseSSEStream } from "./sse.js";
import type {
  AnalyticsResponse,
  BatchDeleteBody,
  BatchDeleteDocumentsResponse,
  BatchQueryBody,
  BatchStatusResponse,
  BatchQueryResponse,
  Collection,
  CollectionListResponse,
  CreateCollectionBody,
  CreateWebhookBody,
  CreateWebhookResponse,
  DeleteResponse,
  Document,
  DocumentChunkListResponse,
  DocumentListOptions,
  DocumentListResponse,
  EmbeddingModelListResponse,
  FileInput,
  HealthResponse,
  MultiQueryBody,
  MultiQueryResponse,
  ProgressEvent,
  QueryBody,
  QueryResponse,
  QueueStatsResponse,
  ReadinessResponse,
  StatusResponse,
  UpdateCollectionBody,
  UpdateWebhookBody,
  UpsertResponse,
  VectorEntry,
  Webhook,
  WebhookDeliveryListResponse,
  WebhookListResponse,
  WebhookTestResponse,
} from "./types.js";

const DEFAULT_BASE_URL = "http://localhost:6100";
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

  private async _fetchWithRetry(
    url: string,
    init: RequestInit,
  ): Promise<Response> {
    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        await sleep(Math.min(0.5 * 2 ** attempt, 4) * 1000);
      }

      let response: Response;
      try {
        response = await this._fetch(url, {
          ...init,
          signal: AbortSignal.timeout(this.timeout),
        });
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (
          lastError.name === "TimeoutError" ||
          lastError.name === "AbortError"
        ) {
          if (attempt < this.maxRetries) continue;
          throw new APITimeoutError(lastError.message);
        }
        if (attempt < this.maxRetries) continue;
        throw new APIConnectionError(lastError.message);
      }

      if (response.status >= 500 && attempt < this.maxRetries) {
        lastError = new Error(
          await response.text().catch(() => "Server error"),
        );
        continue;
      }

      if (response.status === 429 && attempt < this.maxRetries) {
        lastError = new Error("Rate limited");
        continue;
      }

      if (response.status >= 400) {
        await this._throwForStatus(response);
      }

      return response;
    }

    throw new APIConnectionError(lastError?.message ?? "Request failed");
  }

  private async _throwForStatus(response: Response): Promise<never> {
    let errBody: {
      detail?: string;
      error?: { message?: string; code?: string };
      message?: string;
    };
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

  private async _request<T>(
    method: string,
    path: string,
    opts?: { json?: unknown; params?: Record<string, string> },
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (opts?.params) {
      url += `?${new URLSearchParams(opts.params)}`;
    }

    const headers: Record<string, string> = { ...this._headers() };
    let body: string | undefined;
    if (opts?.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    }

    const response = await this._fetchWithRetry(url, { method, headers, body });

    if (response.status === 204) return { status: "ok" } as T;
    const text = await response.text();
    if (!text) return { status: "ok" } as T;
    return JSON.parse(text) as T;
  }

  private async _requestFormData<T>(
    path: string,
    formData: FormData,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await this._fetchWithRetry(url, {
      method: "POST",
      headers: this._headers(),
      body: formData,
    });
    return (await response.json()) as T;
  }

  private async _requestText(path: string): Promise<string> {
    const url = `${this.baseUrl}${path}`;
    const response = await this._fetchWithRetry(url, {
      method: "GET",
      headers: this._headers(),
    });
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
      form.append("file", new Blob([file as BlobPart]), "document");
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

  readiness(): Promise<ReadinessResponse> {
    return this._request("GET", "/health/ready");
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

  async batchUploadDocuments(
    collection: string,
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    const form = new FormData();

    for (const file of files) {
      if (file instanceof Blob) {
        const name = file instanceof File ? file.name : "document";
        form.append("files", file, name);
      } else if (file instanceof Uint8Array || (typeof Buffer !== "undefined" && Buffer.isBuffer(file))) {
        form.append("files", new Blob([file as BlobPart]), "document");
      } else if (typeof file === "object" && "path" in file) {
        const { readFile } = await import("node:fs/promises");
        const { basename } = await import("node:path");
        const data = await readFile(file.path);
        const name = file.name ?? basename(file.path);
        form.append("files", new Blob([data]), name);
      }
    }

    if (metadata) {
      form.append("metadata", JSON.stringify(metadata));
    }

    return this._requestFormData(
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/upload`,
      form,
    );
  }

  batchGetStatus(
    collection: string,
    documentIds: string[],
  ): Promise<BatchStatusResponse> {
    return this._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/status`,
      { json: { document_ids: documentIds } },
    );
  }

  batchDeleteDocuments(
    collection: string,
    documentIds: string[],
  ): Promise<BatchDeleteDocumentsResponse> {
    return this._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/delete`,
      { json: { document_ids: documentIds } },
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

  // ---- Queue ----

  getQueueStats(): Promise<QueueStatsResponse> {
    return this._request("GET", "/v1/queue/stats");
  }

  // ---- Webhooks ----

  createWebhook(body: CreateWebhookBody): Promise<CreateWebhookResponse> {
    return this._request("POST", "/v1/admin/webhooks", { json: body });
  }

  listWebhooks(): Promise<WebhookListResponse> {
    return this._request("GET", "/v1/admin/webhooks");
  }

  getWebhook(id: string): Promise<Webhook> {
    return this._request(
      "GET",
      `/v1/admin/webhooks/${encodeURIComponent(id)}`,
    );
  }

  updateWebhook(id: string, body: UpdateWebhookBody): Promise<Webhook> {
    return this._request(
      "PUT",
      `/v1/admin/webhooks/${encodeURIComponent(id)}`,
      { json: body },
    );
  }

  deleteWebhook(id: string): Promise<StatusResponse> {
    return this._request(
      "DELETE",
      `/v1/admin/webhooks/${encodeURIComponent(id)}`,
    );
  }

  listWebhookDeliveries(
    id: string,
    options?: { limit?: number; offset?: number },
  ): Promise<WebhookDeliveryListResponse> {
    const params: Record<string, string> = {};
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._request(
      "GET",
      `/v1/admin/webhooks/${encodeURIComponent(id)}/deliveries`,
      { params },
    );
  }

  testWebhook(id: string): Promise<WebhookTestResponse> {
    return this._request(
      "POST",
      `/v1/admin/webhooks/${encodeURIComponent(id)}/test`,
    );
  }

  // ---- Multi-Collection Query ----

  multiQuery(body: MultiQueryBody): Promise<MultiQueryResponse> {
    return this._request("POST", "/v1/query", { json: body });
  }

  // ---- Batch Query ----

  batchQuery(body: BatchQueryBody): Promise<BatchQueryResponse> {
    return this._request("POST", "/v1/batch/query", { json: body });
  }

  // ---- Analytics ----

  getAnalytics(collection: string): Promise<AnalyticsResponse> {
    return this._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/analytics`,
    );
  }

  // ---- Collection-Scoped Client ----

  collection(name: string): CollectionClient {
    return new CollectionClient(this, name);
  }
}

export class CollectionClient {
  constructor(
    private readonly client: BigRAG,
    private readonly name: string,
  ) {}

  upload(
    file: FileInput,
    metadata?: Record<string, unknown>,
  ): Promise<Document> {
    return this.client.uploadDocument(this.name, file, metadata);
  }

  listDocuments(options?: DocumentListOptions): Promise<DocumentListResponse> {
    return this.client.listDocuments(this.name, options);
  }

  getDocument(documentId: string): Promise<Document> {
    return this.client.getDocument(this.name, documentId);
  }

  deleteDocument(documentId: string): Promise<StatusResponse> {
    return this.client.deleteDocument(this.name, documentId);
  }

  batchUpload(
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    return this.client.batchUploadDocuments(this.name, files, metadata);
  }

  batchGetStatus(documentIds: string[]): Promise<BatchStatusResponse> {
    return this.client.batchGetStatus(this.name, documentIds);
  }

  batchDelete(documentIds: string[]): Promise<BatchDeleteDocumentsResponse> {
    return this.client.batchDeleteDocuments(this.name, documentIds);
  }

  reprocessDocument(documentId: string): Promise<StatusResponse> {
    return this.client.reprocessDocument(this.name, documentId);
  }

  getDocumentChunks(documentId: string): Promise<DocumentChunkListResponse> {
    return this.client.getDocumentChunks(this.name, documentId);
  }

  query(body: QueryBody): Promise<QueryResponse> {
    return this.client.query(this.name, body);
  }

  analytics(): Promise<AnalyticsResponse> {
    return this.client.getAnalytics(this.name);
  }

  streamDocumentProgress(
    documentId: string,
  ): AsyncGenerator<ProgressEvent> {
    return this.client.streamDocumentProgress(this.name, documentId);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
