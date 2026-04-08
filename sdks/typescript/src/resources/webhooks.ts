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

/**
 * Resource namespace for webhook management.
 *
 * Access via `client.webhooks`.
 */
export class WebhooksResource {
  /** @internal */
  constructor(private readonly _client: RequestClient) {}

  /**
   * Register a new webhook.
   *
   * @param body - Webhook configuration including URL, events, and optional collections filter.
   */
  create(body: CreateWebhookBody): Promise<CreateWebhookResponse> {
    return this._client._request("POST", "/v1/admin/webhooks", { json: body });
  }

  /**
   * List all registered webhooks.
   */
  list(): Promise<WebhookListResponse> {
    return this._client._request("GET", "/v1/admin/webhooks");
  }

  /**
   * Retrieve a single webhook by ID.
   *
   * @param id - The webhook ID.
   */
  get(id: string): Promise<Webhook> {
    return this._client._request("GET", `/v1/admin/webhooks/${encodeURIComponent(id)}`);
  }

  /**
   * Update an existing webhook.
   *
   * @param id - The webhook ID.
   * @param body - Fields to update.
   */
  update(id: string, body: UpdateWebhookBody): Promise<Webhook> {
    return this._client._request("PUT", `/v1/admin/webhooks/${encodeURIComponent(id)}`, {
      json: body,
    });
  }

  /**
   * Delete a webhook.
   *
   * @param id - The webhook ID.
   */
  delete(id: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/webhooks/${encodeURIComponent(id)}`);
  }

  /**
   * List delivery attempts for a webhook.
   *
   * @param id - The webhook ID.
   * @param options - Optional pagination with `limit` and `offset`.
   */
  listDeliveries(
    id: string,
    options?: { limit?: number; offset?: number },
  ): Promise<WebhookDeliveryListResponse> {
    const params: Record<string, string> = {};
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request(
      "GET",
      `/v1/admin/webhooks/${encodeURIComponent(id)}/deliveries`,
      { params },
    );
  }

  /**
   * Send a test payload to a webhook endpoint.
   *
   * @param id - The webhook ID.
   */
  test(id: string): Promise<WebhookTestResponse> {
    return this._client._request("POST", `/v1/admin/webhooks/${encodeURIComponent(id)}/test`);
  }
}
