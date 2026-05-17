import type { RequestClient } from "../../core.js";
import type { AccessLogListResponse, AccessLogOverviewResponse } from "../../types/index.js";
import { pagination } from "./_shared.js";

export class AdminAccessResource {
  constructor(private readonly _client: RequestClient) {}

  logs(
    options: {
      action?: string;
      actorId?: string;
      collection?: string;
      method?: string;
      path?: string;
      statusFamily?: string;
      success?: boolean;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<AccessLogListResponse> {
    const params = pagination(options);
    if (options.action !== undefined) params.action = options.action;
    if (options.actorId !== undefined) params.actor_id = options.actorId;
    if (options.collection !== undefined) params.collection = options.collection;
    if (options.method !== undefined) params.method = options.method;
    if (options.path !== undefined) params.path = options.path;
    if (options.statusFamily !== undefined) params.status_family = options.statusFamily;
    if (options.success !== undefined) params.success = String(options.success);
    return this._client._request("GET", "/v1/admin/access/logs", { params });
  }

  overview(options: { windowDays?: number } = {}): Promise<AccessLogOverviewResponse> {
    const params: Record<string, string> = {};
    if (options.windowDays !== undefined) params.window_days = String(options.windowDays);
    return this._client._request("GET", "/v1/admin/access/overview", { params });
  }
}
