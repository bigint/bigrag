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

export class BigRAG extends BigRAGCore {
  readonly collections: CollectionsResource;
  readonly documents: DocumentsResource;
  readonly queries: QueryResource;
  readonly vectors: VectorsResource;
  readonly webhooks: WebhooksResource;

  constructor(options: BigRAGOptions = {}) {
    super(options);
    this.collections = new CollectionsResource(this);
    this.documents = new DocumentsResource(this);
    this.queries = new QueryResource(this);
    this.vectors = new VectorsResource(this);
    this.webhooks = new WebhooksResource(this);
  }

  health(): Promise<HealthResponse> {
    return this._request("GET", "/health");
  }

  readiness(): Promise<ReadinessResponse> {
    return this._request("GET", "/health/ready");
  }

  getStats(): Promise<PlatformStatsResponse> {
    return this._request("GET", "/v1/stats");
  }

  listEmbeddingModels(): Promise<EmbeddingModelListResponse> {
    return this._request("GET", "/v1/embeddings/models");
  }

  getAnalytics(collection: string): Promise<AnalyticsResponse> {
    return this._request("GET", `/v1/collections/${encodeURIComponent(collection)}/analytics`);
  }

  listCollections(options?: CollectionListOptions): Promise<CollectionListResponse> {
    return this.collections.list(options);
  }

  getCollectionStats(name: string): Promise<CollectionStatsResponse> {
    return this.collections.stats(name);
  }

  createCollection(body: CreateCollectionBody): Promise<Collection> {
    return this.collections.create(body);
  }

  getCollection(name: string): Promise<Collection> {
    return this.collections.get(name);
  }

  updateCollection(name: string, body: UpdateCollectionBody): Promise<Collection> {
    return this.collections.update(name, body);
  }

  deleteCollection(name: string): Promise<StatusResponse> {
    return this.collections.delete(name);
  }

  uploadDocument(
    collection: string,
    file: FileInput,
    metadata?: Record<string, unknown>,
  ): Promise<Document> {
    return this.documents.upload(collection, file, metadata);
  }

  listDocuments(collection: string, options?: DocumentListOptions): Promise<DocumentListResponse> {
    return this.documents.list(collection, options);
  }

  getDocument(collection: string, documentId: string): Promise<Document> {
    return this.documents.get(collection, documentId);
  }

  deleteDocument(collection: string, documentId: string): Promise<StatusResponse> {
    return this.documents.delete(collection, documentId);
  }

  batchUploadDocuments(
    collection: string,
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    return this.documents.batchUpload(collection, files, metadata);
  }

  batchGetStatus(collection: string, documentIds: string[]): Promise<BatchStatusResponse> {
    return this.documents.batchGetStatus(collection, documentIds);
  }

  batchGetDocuments(collection: string, documentIds: string[]): Promise<BatchGetDocumentsResponse> {
    return this.documents.batchGet(collection, documentIds);
  }

  batchDeleteDocuments(
    collection: string,
    documentIds: string[],
  ): Promise<BatchDeleteDocumentsResponse> {
    return this.documents.batchDelete(collection, documentIds);
  }

  reprocessDocument(collection: string, documentId: string): Promise<StatusResponse> {
    return this.documents.reprocess(collection, documentId);
  }

  getDocumentChunks(collection: string, documentId: string): Promise<DocumentChunkListResponse> {
    return this.documents.getChunks(collection, documentId);
  }

  getDocumentFileUrl(collection: string, documentId: string): string {
    return this.documents.getFileUrl(collection, documentId);
  }

  streamDocumentProgress(collection: string, documentId: string): AsyncGenerator<ProgressEvent> {
    return this.documents.streamProgress(collection, documentId);
  }

  query(collection: string, body: QueryBody): Promise<QueryResponse> {
    return this.queries.query(collection, body);
  }

  upsertVectors(collection: string, vectors: VectorEntry[]): Promise<UpsertResponse> {
    return this.vectors.upsert(collection, vectors);
  }

  deleteVectors(collection: string, ids: string[]): Promise<DeleteResponse> {
    return this.vectors.delete(collection, ids);
  }

  createWebhook(body: CreateWebhookBody): Promise<CreateWebhookResponse> {
    return this.webhooks.create(body);
  }

  listWebhooks(): Promise<WebhookListResponse> {
    return this.webhooks.list();
  }

  getWebhook(id: string): Promise<Webhook> {
    return this.webhooks.get(id);
  }

  updateWebhook(id: string, body: UpdateWebhookBody): Promise<Webhook> {
    return this.webhooks.update(id, body);
  }

  deleteWebhook(id: string): Promise<StatusResponse> {
    return this.webhooks.delete(id);
  }

  listWebhookDeliveries(
    id: string,
    options?: { limit?: number; offset?: number },
  ): Promise<WebhookDeliveryListResponse> {
    return this.webhooks.listDeliveries(id, options);
  }

  testWebhook(id: string): Promise<WebhookTestResponse> {
    return this.webhooks.test(id);
  }

  multiQuery(body: MultiQueryBody): Promise<MultiQueryResponse> {
    return this.queries.multiQuery(body);
  }

  batchQuery(body: BatchQueryBody): Promise<BatchQueryResponse> {
    return this.queries.batchQuery(body);
  }

  collection(name: string): CollectionClient {
    return new CollectionClient(this, name);
  }
}

export class CollectionClient {
  constructor(
    private readonly client: BigRAG,
    private readonly name: string,
  ) {}

  upload(file: FileInput, metadata?: Record<string, unknown>): Promise<Document> {
    return this.client.documents.upload(this.name, file, metadata);
  }

  listDocuments(options?: DocumentListOptions): Promise<DocumentListResponse> {
    return this.client.documents.list(this.name, options);
  }

  getDocument(documentId: string): Promise<Document> {
    return this.client.documents.get(this.name, documentId);
  }

  deleteDocument(documentId: string): Promise<StatusResponse> {
    return this.client.documents.delete(this.name, documentId);
  }

  batchUpload(
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    return this.client.documents.batchUpload(this.name, files, metadata);
  }

  batchGetStatus(documentIds: string[]): Promise<BatchStatusResponse> {
    return this.client.documents.batchGetStatus(this.name, documentIds);
  }

  batchGetDocuments(documentIds: string[]): Promise<BatchGetDocumentsResponse> {
    return this.client.documents.batchGet(this.name, documentIds);
  }

  stats(): Promise<CollectionStatsResponse> {
    return this.client.collections.stats(this.name);
  }

  batchDelete(documentIds: string[]): Promise<BatchDeleteDocumentsResponse> {
    return this.client.documents.batchDelete(this.name, documentIds);
  }

  reprocessDocument(documentId: string): Promise<StatusResponse> {
    return this.client.documents.reprocess(this.name, documentId);
  }

  getDocumentChunks(documentId: string): Promise<DocumentChunkListResponse> {
    return this.client.documents.getChunks(this.name, documentId);
  }

  query(body: QueryBody): Promise<QueryResponse> {
    return this.client.queries.query(this.name, body);
  }

  analytics(): Promise<AnalyticsResponse> {
    return this.client.getAnalytics(this.name);
  }

  streamDocumentProgress(documentId: string): AsyncGenerator<ProgressEvent> {
    return this.client.documents.streamProgress(this.name, documentId);
  }

  streamEvents(): AsyncGenerator<ProgressEvent> {
    return this.client.collections.streamEvents(this.name);
  }
}
