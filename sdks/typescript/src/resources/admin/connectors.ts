import type { RequestClient } from "../../core.js";
import type { GoogleConnectorConfig, UpdateGoogleConnectorConfigBody } from "../../types/index.js";

export class AdminConnectorsResource {
  readonly google: AdminGoogleConnectorResource;

  constructor(client: RequestClient) {
    this.google = new AdminGoogleConnectorResource(client);
  }
}

export class AdminGoogleConnectorResource {
  constructor(private readonly _client: RequestClient) {}

  get(): Promise<GoogleConnectorConfig> {
    return this._client._request("GET", "/v1/admin/connectors/google");
  }

  update(body: UpdateGoogleConnectorConfigBody): Promise<GoogleConnectorConfig> {
    return this._client._request("PUT", "/v1/admin/connectors/google", { json: body });
  }
}
