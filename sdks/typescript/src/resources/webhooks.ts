import type { RequestClient } from "../core.js";
import type {
  CreateWebhookBody,
  CreateWebhookResponse,
  StatusResponse,
  UpdateWebhookBody,
  Webhook,
  WebhookDeliveryListResponse,
  WebhookListResponse,
  WebhookTestResponse,
} from "../types.js";

export class WebhooksResource {
  constructor(private readonly _client: RequestClient) {}

  create(body: CreateWebhookBody): Promise<CreateWebhookResponse> {
    return this._client._request("POST", "/v1/admin/webhooks", { json: body });
  }

  list(): Promise<WebhookListResponse> {
    return this._client._request("GET", "/v1/admin/webhooks");
  }

  get(id: string): Promise<Webhook> {
    return this._client._request("GET", `/v1/admin/webhooks/${encodeURIComponent(id)}`);
  }

  update(id: string, body: UpdateWebhookBody): Promise<Webhook> {
    return this._client._request("PUT", `/v1/admin/webhooks/${encodeURIComponent(id)}`, {
      json: body,
    });
  }

  delete(id: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/webhooks/${encodeURIComponent(id)}`);
  }

  listDeliveries(
    id: string,
    options?: { limit?: number; offset?: number },
  ): Promise<WebhookDeliveryListResponse> {
    const params: Record<string, string> = {};
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request("GET", `/v1/admin/webhooks/${encodeURIComponent(id)}/deliveries`, {
      params,
    });
  }

  test(id: string): Promise<WebhookTestResponse> {
    return this._client._request("POST", `/v1/admin/webhooks/${encodeURIComponent(id)}/test`);
  }

  replayDelivery(id: string, deliveryId: string): Promise<WebhookTestResponse> {
    return this._client._request(
      "POST",
      `/v1/admin/webhooks/${encodeURIComponent(id)}/deliveries/${encodeURIComponent(deliveryId)}/replay`,
    );
  }
}
