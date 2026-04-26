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
  EmbeddingModelListResponse,
  HealthResponse,
  PlatformStatsResponse,
  ReadinessResponse,
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
}
