import type { RequestClient } from "../../core.js";
import type {
  InstanceSettingsResponse,
  InstanceSettingsTestResponse,
  ResetInstanceSettingsBody,
  StatusResponse,
  TestInstanceSettingsBody,
  UpdateInstanceSettingsBody,
} from "../../types/index.js";

export class AdminSettingsResource {
  constructor(private readonly _client: RequestClient) {}

  list(): Promise<InstanceSettingsResponse> {
    return this._client._request("GET", "/v1/admin/settings");
  }

  update(body: UpdateInstanceSettingsBody): Promise<InstanceSettingsResponse> {
    return this._client._request("PUT", "/v1/admin/settings", { json: body });
  }

  test(body: TestInstanceSettingsBody = {}): Promise<InstanceSettingsTestResponse> {
    return this._client._request("POST", "/v1/admin/settings/test", {
      json: { values: body.values ?? {} },
    });
  }

  reset(body: ResetInstanceSettingsBody = { keys: [] }): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/admin/settings/reset", { json: body });
  }

  purgeEmbeddingCache(): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/admin/settings/embedding-cache/purge");
  }
}
