import type { RequestClient } from "../core.js";
import { BigRAGRealtimeConnection } from "../realtime.js";
import type {
  AnalyticsResponse,
  Collection,
  CollectionListOptions,
  CollectionListResponse,
  CollectionRealtimeTokenResponse,
  CollectionStatsResponse,
  CreateCollectionBody,
  ProgressEvent,
  StatusResponse,
  UpdateCollectionBody,
} from "../types/index.js";

export class CollectionsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options?: CollectionListOptions): Promise<CollectionListResponse> {
    const params: Record<string, string> = {};
    if (options?.name) params.name = options.name;
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    if (options?.include_total !== undefined) {
      params.include_total = options.include_total ? "true" : "false";
    }
    return this._client._request("GET", "/v1/collections", { params });
  }

  async *listAll(options?: Omit<CollectionListOptions, "offset">): AsyncGenerator<Collection> {
    const pageSize = options?.limit ?? 100;
    let offset = 0;
    while (true) {
      const page = await this.list({ ...options, limit: pageSize, offset });
      for (const c of page.collections) yield c;
      if (page.collections.length < pageSize) return;
      offset += page.collections.length;
      if (page.total !== null && offset >= page.total) return;
    }
  }

  get(name: string): Promise<Collection> {
    return this._client._request("GET", `/v1/collections/${encodeURIComponent(name)}`);
  }

  create(body: CreateCollectionBody): Promise<Collection> {
    return this._client._request("POST", "/v1/collections", { json: body });
  }

  update(name: string, body: UpdateCollectionBody): Promise<Collection> {
    return this._client._request("PUT", `/v1/collections/${encodeURIComponent(name)}`, {
      json: body,
    });
  }

  delete(name: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/collections/${encodeURIComponent(name)}`);
  }

  stats(name: string): Promise<CollectionStatsResponse> {
    return this._client._request("GET", `/v1/collections/${encodeURIComponent(name)}/stats`);
  }

  truncate(name: string): Promise<StatusResponse> {
    return this._client._request("POST", `/v1/collections/${encodeURIComponent(name)}/truncate`);
  }

  analytics(name: string): Promise<AnalyticsResponse> {
    return this._client._request("GET", `/v1/collections/${encodeURIComponent(name)}/analytics`);
  }

  createRealtimeToken(name: string): Promise<CollectionRealtimeTokenResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(name)}/realtime-token`,
    );
  }

  async *streamEvents(
    name: string,
    options: { token?: string } = {},
  ): AsyncGenerator<ProgressEvent> {
    const connection = new BigRAGRealtimeConnection(this._client);
    try {
      for await (const message of connection.subscribe<ProgressEvent>("collection.events", {
        collection: name,
        token: options.token,
      })) {
        if (message.type === "event") yield message.payload;
        if (message.type === "error") throw new Error(message.message);
        if (message.type === "complete") return;
      }
    } finally {
      await connection.close();
    }
  }
}
