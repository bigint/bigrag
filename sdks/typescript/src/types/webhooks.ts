export type WebhookEvent =
  | "document.processing"
  | "document.ready"
  | "document.failed"
  | "document.deleted"
  | "collection.created"
  | "collection.updated"
  | "collection.deleted"
  | "collection.truncated"
  | "connector.sync.started"
  | "connector.sync.completed"
  | "connector.sync.failed"
  | "connector.sync.needs_reauth"
  | "backup.started"
  | "backup.succeeded"
  | "backup.failed";

export interface Webhook {
  id: string;
  url: string;
  events: WebhookEvent[];
  collections: string[] | null;
  active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateWebhookBody {
  url: string;
  events: WebhookEvent[];
  collections?: string[];
}

export interface CreateWebhookResponse extends Webhook {
  secret: string;
}

export interface UpdateWebhookBody {
  url?: string;
  events?: WebhookEvent[];
  collections?: string[] | null;
  active?: boolean;
}

export interface WebhookListResponse {
  webhooks: Webhook[];
  total: number;
}

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

export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[];
  total: number;
}

export interface WebhookTestResponse {
  status: string;
  status_code: number | null;
  error: string | null;
  duration_ms?: number;
}
