import type { RequestClient } from "../core.js";
import { USER_AGENT } from "../core.js";
import { errorForStatus } from "../errors.js";
import { parseSSEStream } from "../sse.js";
import type {
  Collection,
  CollectionListOptions,
  CollectionListResponse,
  CollectionStatsResponse,
  CreateCollectionBody,
  ProgressEvent,
  StatusResponse,
  UpdateCollectionBody,
} from "../types.js";

/**
 * Resource namespace for collection management.
 *
 * Access via `client.collections`.
 */
export class CollectionsResource {
  /** @internal */
  constructor(private readonly _client: RequestClient) {}

  /**
   * List collections with optional filtering and pagination.
   *
   * @param options - Optional filters such as `name`, `limit`, and `offset`.
   * @returns A paginated list of collections.
   */
  list(options?: CollectionListOptions): Promise<CollectionListResponse> {
    const params: Record<string, string> = {};
    if (options?.name) params.name = options.name;
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request("GET", "/v1/collections", { params });
  }

  /**
   * Auto-paginate every collection. Useful for batch operations across
   * all collections without manual offset tracking.
   */
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

  /**
   * Retrieve a single collection by name.
   *
   * @param name - The collection name.
   */
  get(name: string): Promise<Collection> {
    return this._client._request("GET", `/v1/collections/${encodeURIComponent(name)}`);
  }

  /**
   * Create a new collection.
   *
   * @param body - Collection configuration including name, embedding settings, and defaults.
   */
  create(body: CreateCollectionBody): Promise<Collection> {
    return this._client._request("POST", "/v1/collections", { json: body });
  }

  /**
   * Update an existing collection.
   *
   * @param name - The collection name.
   * @param body - Fields to update.
   */
  update(name: string, body: UpdateCollectionBody): Promise<Collection> {
    return this._client._request("PUT", `/v1/collections/${encodeURIComponent(name)}`, {
      json: body,
    });
  }

  /**
   * Delete a collection and all its documents.
   *
   * @param name - The collection name.
   */
  delete(name: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/collections/${encodeURIComponent(name)}`);
  }

  /**
   * Get statistics for a collection (document counts, chunk totals, etc.).
   *
   * @param name - The collection name.
   */
  stats(name: string): Promise<CollectionStatsResponse> {
    return this._client._request("GET", `/v1/collections/${encodeURIComponent(name)}/stats`);
  }

  /**
   * Truncate a collection — delete all documents, vectors, and S3 jobs but keep the collection.
   *
   * @param name - The collection name.
   */
  truncate(name: string): Promise<StatusResponse> {
    return this._client._request("POST", `/v1/collections/${encodeURIComponent(name)}/truncate`);
  }

  /**
   * Stream real-time events for all activity in a collection via SSE.
   *
   * @param name - The collection name.
   * @yields {@link ProgressEvent} objects as they arrive (document ingestion, S3 imports, etc.).
   */
  async *streamEvents(name: string): AsyncGenerator<ProgressEvent> {
    const path = `/v1/collections/${encodeURIComponent(name)}/events`;
    const tokenParam = this._client.apiKey
      ? `?token=${encodeURIComponent(this._client.apiKey)}`
      : "";
    const url = `${this._client.baseUrl}${path}${tokenParam}`;

    const response = await this._client._fetch(url, {
      method: "GET",
      headers: { "User-Agent": USER_AGENT },
    });

    if (!response.ok) {
      throw errorForStatus(response.status, response.statusText);
    }

    yield* parseSSEStream(response);
  }
}
