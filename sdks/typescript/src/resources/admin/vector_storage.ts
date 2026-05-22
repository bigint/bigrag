import type { RequestClient } from "../../core.js";
import type { VectorStorageOverviewResponse } from "../../types/index.js";

export class AdminVectorStorageResource {
  constructor(private readonly _client: RequestClient) {}

  overview(): Promise<VectorStorageOverviewResponse> {
    return this._client._request("GET", "/v1/admin/vector-storage/overview");
  }
}
