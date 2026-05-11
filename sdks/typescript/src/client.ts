import type { BigRAGOptions } from "./core.js";
import { BigRAGCore } from "./core.js";
import {
  AdminResource,
  AuthResource,
  ChatResource,
  CollectionsResource,
  ConnectorsResource,
  DocumentsResource,
  EvaluationsResource,
  QueryResource,
  VectorsResource,
  WebhooksResource,
} from "./resources/index.js";
import type {
  EmbeddingModelListResponse,
  HealthResponse,
  PlatformStatsResponse,
  ReadinessResponse,
  UsageResponse,
} from "./types.js";

export class BigRAG extends BigRAGCore {
  readonly admin: AdminResource;
  readonly auth: AuthResource;
  readonly collections: CollectionsResource;
  readonly chat: ChatResource;
  readonly connectors: ConnectorsResource;
  readonly documents: DocumentsResource;
  readonly evaluations: EvaluationsResource;
  readonly queries: QueryResource;
  readonly vectors: VectorsResource;
  readonly webhooks: WebhooksResource;

  constructor(options: BigRAGOptions = {}) {
    super(options);
    this.admin = new AdminResource(this);
    this.auth = new AuthResource(this);
    this.chat = new ChatResource(this);
    this.collections = new CollectionsResource(this);
    this.connectors = new ConnectorsResource(this);
    this.documents = new DocumentsResource(this);
    this.evaluations = new EvaluationsResource(this);
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

  getUsage(options: { windowDays?: number } = {}): Promise<UsageResponse> {
    const params: Record<string, string> = {};
    if (options.windowDays !== undefined) params.window_days = String(options.windowDays);
    return this._request("GET", "/v1/usage", { params });
  }
}
