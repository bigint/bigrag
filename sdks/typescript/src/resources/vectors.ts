import type { RequestClient } from "../core.js";
import type { DeleteResponse, UpsertResponse, VectorEntry } from "../types/index.js";

export class VectorsResource {
  constructor(private readonly _client: RequestClient) {}

  upsert(collection: string, vectors: VectorEntry[]): Promise<UpsertResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/vectors/upsert`,
      { json: { vectors } },
    );
  }

  delete(collection: string, ids: string[]): Promise<DeleteResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/vectors/delete`,
      { json: { ids } },
    );
  }
}
