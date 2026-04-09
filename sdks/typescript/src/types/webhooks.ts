/** A registered webhook. */
export interface Webhook {
  id: string;
  url: string;
  events: string[];
  collections: string[] | null;
  description: string;
  active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

/** Body for creating a new webhook. */
export interface CreateWebhookBody {
  url: string;
  events: string[];
  collections?: string[];
  description?: string;
}

/** Response when creating a webhook -- includes the signing secret. */
export interface CreateWebhookResponse extends Webhook {
  secret: string;
}

/** Body for updating an existing webhook. */
export interface UpdateWebhookBody {
  url?: string;
  events?: string[];
  collections?: string[] | null;
  description?: string;
  active?: boolean;
}

/** Response listing webhooks. */
export interface WebhookListResponse {
  webhooks: Webhook[];
}

/** A single webhook delivery attempt. */
export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event: string;
  payload: Record<string, unknown>;
  status: string;
  attempts: number;
  last_status_code: number | null;
  last_error: string | null;
  created_at: string;
  completed_at: string | null;
}

/** Paginated list of webhook deliveries. */
export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[];
  total: number;
}

/** Response from testing a webhook endpoint. */
export interface WebhookTestResponse {
  status: string;
  status_code: number | null;
  error: string | null;
}
