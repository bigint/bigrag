import type { RequestClient } from "../core.js";
import type {
  Collection,
  CollectionListOptions,
  CollectionListResponse,
  CollectionStatsResponse,
  CreateCollectionBody,
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
}
