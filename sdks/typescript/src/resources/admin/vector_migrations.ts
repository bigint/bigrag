import type { RequestClient } from "../../core.js";
import type {
  StatusResponse,
  VectorMigrationCreateBody,
  VectorMigrationJob,
  VectorMigrationJobListResponse,
} from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminVectorMigrationsResource {
  constructor(private readonly _client: RequestClient) {}

  list(
    options: { collection?: string; limit?: number; offset?: number } = {},
  ): Promise<VectorMigrationJobListResponse> {
    return this._client._request("GET", "/v1/admin/vector-storage/migrations", {
      params: {
        ...pagination(options),
        ...(options.collection ? { collection: options.collection } : {}),
      },
    });
  }

  get(migrationId: string): Promise<VectorMigrationJob> {
    return this._client._request(
      "GET",
      `/v1/admin/vector-storage/migrations/${encodeURIComponent(migrationId)}`,
    );
  }

  create(body: VectorMigrationCreateBody): Promise<VectorMigrationJob> {
    return this._client._request("POST", "/v1/admin/vector-storage/migrations", {
      json: body,
    });
  }

  delete(migrationId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/admin/vector-storage/migrations/${encodeURIComponent(migrationId)}`,
    );
  }
}
