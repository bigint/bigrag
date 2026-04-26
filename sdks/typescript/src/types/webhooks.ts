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

export interface CreateWebhookBody {
  url: string;
  events: string[];
  collections?: string[];
  description?: string;
}

export interface CreateWebhookResponse extends Webhook {
  secret: string;
}

export interface UpdateWebhookBody {
  url?: string;
  events?: string[];
  collections?: string[] | null;
  description?: string;
  active?: boolean;
}

export interface WebhookListResponse {
  webhooks: Webhook[];
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
}
