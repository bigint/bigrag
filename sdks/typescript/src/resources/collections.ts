import type { RequestClient } from "../core.js";
import { USER_AGENT } from "../core.js";
import { errorForStatus } from "../errors.js";
import { parseSSEStream } from "../sse.js";
import type {
  AnalyticsResponse,
  Collection,
  CollectionListOptions,
  CollectionListResponse,
  CollectionStatsResponse,
  CreateCollectionBody,
  ProgressEvent,
  StatusResponse,
  UpdateCollectionBody,
} from "../types.js";

export class CollectionsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options?: CollectionListOptions): Promise<CollectionListResponse> {
    const params: Record<string, string> = {};
    if (options?.name) params.name = options.name;
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
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
      if (offset >= page.total) return;
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

  reembed(name: string): Promise<StatusResponse> {
    return this._client._request("POST", `/v1/collections/${encodeURIComponent(name)}/reembed`);
  }

  analytics(name: string): Promise<AnalyticsResponse> {
    return this._client._request("GET", `/v1/collections/${encodeURIComponent(name)}/analytics`);
  }

  async *streamEvents(name: string): AsyncGenerator<ProgressEvent> {
    const path = `/v1/collections/${encodeURIComponent(name)}/events`;
    const url = `${this._client.baseUrl}${path}`;
    const headers: Record<string, string> = { "User-Agent": USER_AGENT };
    if (this._client.apiKey) headers.Authorization = `Bearer ${this._client.apiKey}`;

    const response = await this._client._fetch(url, {
      method: "GET",
      headers,
    });

    if (!response.ok) {
      const message = await response.text().catch(() => response.statusText);
      throw errorForStatus(response.status, message);
    }

    yield* parseSSEStream(response);
  }
}
