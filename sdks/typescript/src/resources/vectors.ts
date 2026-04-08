import type { RequestClient } from "../core.js";
import type { DeleteResponse, UpsertResponse, VectorEntry } from "../types.js";

/**
 * Resource namespace for raw vector operations.
 *
 * Access via `client.vectors`.
 */
export class VectorsResource {
  /** @internal */
  constructor(private readonly _client: RequestClient) {}

  /**
   * Upsert vectors into a collection.
   *
   * @param collection - The collection name.
   * @param vectors - Array of vector entries to upsert.
   */
  upsert(collection: string, vectors: VectorEntry[]): Promise<UpsertResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/vectors/upsert`,
      { json: { vectors } },
    );
  }

  /**
   * Delete vectors from a collection by ID.
   *
   * @param collection - The collection name.
   * @param ids - Array of vector IDs to delete.
   */
  delete(collection: string, ids: string[]): Promise<DeleteResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/vectors/delete`,
      { json: { ids } },
    );
  }
}
