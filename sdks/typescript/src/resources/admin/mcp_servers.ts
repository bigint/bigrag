import type { RequestClient } from "../../core.js";
import type {
  CreateMcpServerBody,
  CreateMcpServerResponse,
  McpServer,
  McpServerListResponse,
  StatusResponse,
  UpdateMcpServerBody,
} from "../../types/index.js";

export class AdminMcpServersResource {
  constructor(private readonly _client: RequestClient) {}

  list(): Promise<McpServerListResponse> {
    return this._client._request("GET", "/v1/admin/mcp-servers");
  }

  create(body: CreateMcpServerBody): Promise<CreateMcpServerResponse> {
    return this._client._request("POST", "/v1/admin/mcp-servers", { json: body });
  }

  update(serverId: string, body: UpdateMcpServerBody): Promise<McpServer> {
    return this._client._request("PATCH", `/v1/admin/mcp-servers/${encodeURIComponent(serverId)}`, {
      json: body,
    });
  }

  rotate(serverId: string): Promise<CreateMcpServerResponse> {
    return this._client._request(
      "POST",
      `/v1/admin/mcp-servers/${encodeURIComponent(serverId)}/rotate`,
    );
  }

  delete(serverId: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/mcp-servers/${encodeURIComponent(serverId)}`);
  }
}
