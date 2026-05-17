import type { RequestClient } from "../../core.js";
import type { AuditLogListResponse } from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminAuditResource {
  constructor(private readonly _client: RequestClient) {}

  list(
    options: {
      action?: string;
      actorId?: string;
      resourceType?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<AuditLogListResponse> {
    const params = pagination(options);
    if (options.action !== undefined) params.action = options.action;
    if (options.actorId !== undefined) params.actor_id = options.actorId;
    if (options.resourceType !== undefined) params.resource_type = options.resourceType;
    return this._client._request("GET", "/v1/admin/audit", { params });
  }
}
