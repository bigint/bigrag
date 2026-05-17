import type { RequestClient } from "../../core.js";
import type {
  ApiKey,
  ApiKeyListResponse,
  CreateApiKeyBody,
  CreateApiKeyResponse,
  StatusResponse,
  UpdateApiKeyBody,
} from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminApiKeysResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<ApiKeyListResponse> {
    return this._client._request("GET", "/v1/admin/api-keys", { params: pagination(options) });
  }

  create(body: CreateApiKeyBody): Promise<CreateApiKeyResponse> {
    return this._client._request("POST", "/v1/admin/api-keys", { json: body });
  }

  update(keyId: string, body: UpdateApiKeyBody): Promise<ApiKey> {
    return this._client._request("PATCH", `/v1/admin/api-keys/${encodeURIComponent(keyId)}`, {
      json: body,
    });
  }

  rotate(keyId: string): Promise<CreateApiKeyResponse> {
    return this._client._request("POST", `/v1/admin/api-keys/${encodeURIComponent(keyId)}/rotate`);
  }

  delete(keyId: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/api-keys/${encodeURIComponent(keyId)}`);
  }
}
