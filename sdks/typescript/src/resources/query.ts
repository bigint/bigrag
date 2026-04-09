import type { RequestClient } from "../core.js";
import type {
  BatchQueryBody,
  BatchQueryResponse,
  MultiQueryBody,
  MultiQueryResponse,
  QueryBody,
  QueryResponse,
} from "../types.js";

/**
 * Resource namespace for query operations.
 *
 * Access via `client.queries`.
 */
export class QueryResource {
  /** @internal */
  constructor(private readonly _client: RequestClient) {}

  /**
   * Query a single collection.
   *
   * @param collection - The collection name.
   * @param body - Query parameters including the search text, top_k, filters, etc.
   */
  query(collection: string, body: QueryBody): Promise<QueryResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/query`,
      { json: body },
    );
  }

  /**
   * Query across multiple collections simultaneously.
   *
   * @param body - Multi-collection query parameters.
   */
  multiQuery(body: MultiQueryBody): Promise<MultiQueryResponse> {
    return this._client._request("POST", "/v1/query", { json: body });
  }

  /**
   * Execute multiple queries in a single batch request.
   *
   * @param body - Batch of query items, each targeting a specific collection.
   */
  batchQuery(body: BatchQueryBody): Promise<BatchQueryResponse> {
    return this._client._request("POST", "/v1/batch/query", { json: body });
  }
}
