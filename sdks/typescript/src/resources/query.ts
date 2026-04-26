import type { RequestClient } from "../core.js";
import type {
  BatchQueryBody,
  BatchQueryResponse,
  MultiQueryBody,
  MultiQueryResponse,
  QueryBody,
  QueryResponse,
} from "../types.js";

export class QueryResource {
  constructor(private readonly _client: RequestClient) {}

  query(collection: string, body: QueryBody): Promise<QueryResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/query`,
      { json: body },
    );
  }

  multiQuery(body: MultiQueryBody): Promise<MultiQueryResponse> {
    return this._client._request("POST", "/v1/query", { json: body });
  }

  batchQuery(body: BatchQueryBody): Promise<BatchQueryResponse> {
    return this._client._request("POST", "/v1/batch/query", { json: body });
  }
}
