import type { BigRAGOptions } from "./core.js";
import { BigRAGCore } from "./core.js";
import {
  CollectionsResource,
  DocumentsResource,
  QueryResource,
  VectorsResource,
  WebhooksResource,
} from "./resources/index.js";
import type {
  AnalyticsResponse,
  BatchDeleteDocumentsResponse,
  BatchGetDocumentsResponse,
  BatchQueryBody,
  BatchQueryResponse,
  BatchStatusResponse,
  Collection,
  CollectionListOptions,
  CollectionListResponse,
  CollectionStatsResponse,
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
  PlatformStatsResponse,
  ProgressEvent,
  QueryBody,
  QueryResponse,
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

export type { BigRAGOptions };

/**
 * Main bigRAG client.
 *
 * Exposes **resource namespaces** (`collections`, `documents`, `queries`,
 * `vectors`, `webhooks`) following the Stripe SDK pattern, as well as
 * backward-compatible flat methods (marked `@deprecated`).
 *
 * Platform-level endpoints (`health`, `readiness`, `getStats`,
 * `listEmbeddingModels`) remain directly on this class.
 */
export class BigRAG extends BigRAGCore {
  /** Collection management resource. */
  readonly collections: CollectionsResource;
  /** Document management resource. */
  readonly documents: DocumentsResource;
  /** Query resource (single, multi, and batch). */
  readonly queries: QueryResource;
  /** Raw vector operations resource. */
  readonly vectors: VectorsResource;
  /** Webhook management resource. */
  readonly webhooks: WebhooksResource;

  constructor(options: BigRAGOptions = {}) {
    super(options);
    this.collections = new CollectionsResource(this);
    this.documents = new DocumentsResource(this);
    this.queries = new QueryResource(this);
    this.vectors = new VectorsResource(this);
    this.webhooks = new WebhooksResource(this);
  }

  // ---- Platform-level endpoints (not scoped to a resource) ----

  /**
   * Check whether the API server is running.
   *
   * @returns Health status and version.
   */
  health(): Promise<HealthResponse> {
    return this._request("GET", "/health");
  }

  /**
   * Check whether all backing services (Postgres, Milvus, Redis) are reachable.
   *
   * @returns Readiness status for each dependency.
   */
  readiness(): Promise<ReadinessResponse> {
    return this._request("GET", "/health/ready");
  }

  /**
   * Retrieve platform-wide statistics.
   *
   * @returns Collection, document, webhook, and queue counts.
   */
  getStats(): Promise<PlatformStatsResponse> {
    return this._request("GET", "/v1/stats");
  }

  /**
   * List all available embedding models.
   *
   * @returns Array of embedding model information.
   */
  listEmbeddingModels(): Promise<EmbeddingModelListResponse> {
    return this._request("GET", "/v1/embeddings/models");
  }

  /**
   * Retrieve analytics for a specific collection.
   *
   * @param collection - The collection name.
   * @returns Analytics data including query stats and top queries.
   */
  getAnalytics(collection: string): Promise<AnalyticsResponse> {
    return this._request("GET", `/v1/collections/${encodeURIComponent(collection)}/analytics`);
  }

  // ---- Backward-compatible flat methods ----

  /**
   * @deprecated Use `client.collections.list()` instead.
   */
  listCollections(options?: CollectionListOptions): Promise<CollectionListResponse> {
    return this.collections.list(options);
  }

  /**
   * @deprecated Use `client.collections.stats(name)` instead.
   */
  getCollectionStats(name: string): Promise<CollectionStatsResponse> {
    return this.collections.stats(name);
  }

  /**
   * @deprecated Use `client.collections.create(body)` instead.
   */
  createCollection(body: CreateCollectionBody): Promise<Collection> {
    return this.collections.create(body);
  }

  /**
   * @deprecated Use `client.collections.get(name)` instead.
   */
  getCollection(name: string): Promise<Collection> {
    return this.collections.get(name);
  }

  /**
   * @deprecated Use `client.collections.update(name, body)` instead.
   */
  updateCollection(name: string, body: UpdateCollectionBody): Promise<Collection> {
    return this.collections.update(name, body);
  }

  /**
   * @deprecated Use `client.collections.delete(name)` instead.
   */
  deleteCollection(name: string): Promise<StatusResponse> {
    return this.collections.delete(name);
  }

  /**
   * @deprecated Use `client.documents.upload(collection, file, metadata)` instead.
   */
  uploadDocument(
    collection: string,
    file: FileInput,
    metadata?: Record<string, unknown>,
  ): Promise<Document> {
    return this.documents.upload(collection, file, metadata);
  }

  /**
   * @deprecated Use `client.documents.list(collection, options)` instead.
   */
  listDocuments(collection: string, options?: DocumentListOptions): Promise<DocumentListResponse> {
    return this.documents.list(collection, options);
  }

  /**
   * @deprecated Use `client.documents.get(collection, documentId)` instead.
   */
  getDocument(collection: string, documentId: string): Promise<Document> {
    return this.documents.get(collection, documentId);
  }

  /**
   * @deprecated Use `client.documents.delete(collection, documentId)` instead.
   */
  deleteDocument(collection: string, documentId: string): Promise<StatusResponse> {
    return this.documents.delete(collection, documentId);
  }

  /**
   * @deprecated Use `client.documents.batchUpload(collection, files, metadata)` instead.
   */
  batchUploadDocuments(
    collection: string,
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    return this.documents.batchUpload(collection, files, metadata);
  }

  /**
   * @deprecated Use `client.documents.batchGetStatus(collection, documentIds)` instead.
   */
  batchGetStatus(collection: string, documentIds: string[]): Promise<BatchStatusResponse> {
    return this.documents.batchGetStatus(collection, documentIds);
  }

  /**
   * @deprecated Use `client.documents.batchGet(collection, documentIds)` instead.
   */
  batchGetDocuments(collection: string, documentIds: string[]): Promise<BatchGetDocumentsResponse> {
    return this.documents.batchGet(collection, documentIds);
  }

  /**
   * @deprecated Use `client.documents.batchDelete(collection, documentIds)` instead.
   */
  batchDeleteDocuments(
    collection: string,
    documentIds: string[],
  ): Promise<BatchDeleteDocumentsResponse> {
    return this.documents.batchDelete(collection, documentIds);
  }

  /**
   * @deprecated Use `client.documents.reprocess(collection, documentId)` instead.
   */
  reprocessDocument(collection: string, documentId: string): Promise<StatusResponse> {
    return this.documents.reprocess(collection, documentId);
  }

  /**
   * @deprecated Use `client.documents.getChunks(collection, documentId)` instead.
   */
  getDocumentChunks(collection: string, documentId: string): Promise<DocumentChunkListResponse> {
    return this.documents.getChunks(collection, documentId);
  }

  /**
   * @deprecated Use `client.documents.getFileUrl(collection, documentId)` instead.
   */
  getDocumentFileUrl(collection: string, documentId: string): string {
    return this.documents.getFileUrl(collection, documentId);
  }

  /**
   * @deprecated Use `client.documents.streamProgress(collection, documentId)` instead.
   */
  streamDocumentProgress(collection: string, documentId: string): AsyncGenerator<ProgressEvent> {
    return this.documents.streamProgress(collection, documentId);
  }

  /**
   * @deprecated Use `client.queries.query(collection, body)` instead.
   */
  query(collection: string, body: QueryBody): Promise<QueryResponse> {
    return this.queries.query(collection, body);
  }

  /**
   * @deprecated Use `client.vectors.upsert(collection, vectors)` instead.
   */
  upsertVectors(collection: string, vectors: VectorEntry[]): Promise<UpsertResponse> {
    return this.vectors.upsert(collection, vectors);
  }

  /**
   * @deprecated Use `client.vectors.delete(collection, ids)` instead.
   */
  deleteVectors(collection: string, ids: string[]): Promise<DeleteResponse> {
    return this.vectors.delete(collection, ids);
  }

  /**
   * @deprecated Use `client.webhooks.create(body)` instead.
   */
  createWebhook(body: CreateWebhookBody): Promise<CreateWebhookResponse> {
    return this.webhooks.create(body);
  }

  /**
   * @deprecated Use `client.webhooks.list()` instead.
   */
  listWebhooks(): Promise<WebhookListResponse> {
    return this.webhooks.list();
  }

  /**
   * @deprecated Use `client.webhooks.get(id)` instead.
   */
  getWebhook(id: string): Promise<Webhook> {
    return this.webhooks.get(id);
  }

  /**
   * @deprecated Use `client.webhooks.update(id, body)` instead.
   */
  updateWebhook(id: string, body: UpdateWebhookBody): Promise<Webhook> {
    return this.webhooks.update(id, body);
  }

  /**
   * @deprecated Use `client.webhooks.delete(id)` instead.
   */
  deleteWebhook(id: string): Promise<StatusResponse> {
    return this.webhooks.delete(id);
  }

  /**
   * @deprecated Use `client.webhooks.listDeliveries(id, options)` instead.
   */
  listWebhookDeliveries(
    id: string,
    options?: { limit?: number; offset?: number },
  ): Promise<WebhookDeliveryListResponse> {
    return this.webhooks.listDeliveries(id, options);
  }

  /**
   * @deprecated Use `client.webhooks.test(id)` instead.
   */
  testWebhook(id: string): Promise<WebhookTestResponse> {
    return this.webhooks.test(id);
  }

  /**
   * @deprecated Use `client.queries.multiQuery(body)` instead.
   */
  multiQuery(body: MultiQueryBody): Promise<MultiQueryResponse> {
    return this.queries.multiQuery(body);
  }

  /**
   * @deprecated Use `client.queries.batchQuery(body)` instead.
   */
  batchQuery(body: BatchQueryBody): Promise<BatchQueryResponse> {
    return this.queries.batchQuery(body);
  }

  // ---- Collection-Scoped Client ----

  /**
   * Create a scoped client for a specific collection.
   *
   * @param name - The collection name.
   * @returns A {@link CollectionClient} pre-bound to the given collection.
   */
  collection(name: string): CollectionClient {
    return new CollectionClient(this, name);
  }
}

/**
 * A convenience wrapper that scopes all operations to a single collection,
 * delegating to the resource namespaces on the parent {@link BigRAG} client.
 */
export class CollectionClient {
  constructor(
    private readonly client: BigRAG,
    private readonly name: string,
  ) {}

  /** Upload a document to this collection. */
  upload(file: FileInput, metadata?: Record<string, unknown>): Promise<Document> {
    return this.client.documents.upload(this.name, file, metadata);
  }

  /** List documents in this collection. */
  listDocuments(options?: DocumentListOptions): Promise<DocumentListResponse> {
    return this.client.documents.list(this.name, options);
  }

  /** Get a document by ID from this collection. */
  getDocument(documentId: string): Promise<Document> {
    return this.client.documents.get(this.name, documentId);
  }

  /** Delete a document by ID from this collection. */
  deleteDocument(documentId: string): Promise<StatusResponse> {
    return this.client.documents.delete(this.name, documentId);
  }

  /** Upload multiple documents to this collection. */
  batchUpload(
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    return this.client.documents.batchUpload(this.name, files, metadata);
  }

  /** Get the processing status of multiple documents. */
  batchGetStatus(documentIds: string[]): Promise<BatchStatusResponse> {
    return this.client.documents.batchGetStatus(this.name, documentIds);
  }

  /** Retrieve multiple documents by ID. */
  batchGetDocuments(documentIds: string[]): Promise<BatchGetDocumentsResponse> {
    return this.client.documents.batchGet(this.name, documentIds);
  }

  /** Get statistics for this collection. */
  stats(): Promise<CollectionStatsResponse> {
    return this.client.collections.stats(this.name);
  }

  /** Delete multiple documents from this collection. */
  batchDelete(documentIds: string[]): Promise<BatchDeleteDocumentsResponse> {
    return this.client.documents.batchDelete(this.name, documentIds);
  }

  /** Trigger reprocessing of a document. */
  reprocessDocument(documentId: string): Promise<StatusResponse> {
    return this.client.documents.reprocess(this.name, documentId);
  }

  /** Get all chunks for a document. */
  getDocumentChunks(documentId: string): Promise<DocumentChunkListResponse> {
    return this.client.documents.getChunks(this.name, documentId);
  }

  /** Query this collection. */
  query(body: QueryBody): Promise<QueryResponse> {
    return this.client.queries.query(this.name, body);
  }

  /** Get analytics for this collection. */
  analytics(): Promise<AnalyticsResponse> {
    return this.client.getAnalytics(this.name);
  }

  /** Stream real-time processing progress for a document. */
  streamDocumentProgress(documentId: string): AsyncGenerator<ProgressEvent> {
    return this.client.documents.streamProgress(this.name, documentId);
  }
}
