use serde::{Deserialize, Serialize};

/// A registered webhook.
#[derive(Debug, Clone, Deserialize)]
pub struct Webhook {
    /// Unique webhook ID.
    pub id: String,
    /// Webhook endpoint URL.
    pub url: String,
    /// Event types this webhook listens for.
    pub events: Vec<String>,
    /// Collections this webhook is scoped to (`None` means all).
    pub collections: Option<Vec<String>>,
    /// Human-readable description.
    pub description: String,
    /// Whether the webhook is active.
    pub active: bool,
    /// Who created this webhook.
    pub created_by: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Response from creating a webhook (includes the signing secret).
#[derive(Debug, Clone, Deserialize)]
pub struct CreateWebhookResponse {
    /// All webhook fields.
    #[serde(flatten)]
    pub webhook: Webhook,
    /// HMAC signing secret (only returned on creation).
    pub secret: String,
}

/// Body for creating a new webhook.
#[derive(Debug, Clone, Serialize)]
pub struct CreateWebhookBody {
    /// Webhook endpoint URL (required).
    pub url: String,
    /// Event types to listen for (required).
    pub events: Vec<String>,
    /// Collections to scope to (`None` means all).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collections: Option<Vec<String>>,
    /// Description.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

/// Body for updating a webhook.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateWebhookBody {
    /// Updated URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    /// Updated event types.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub events: Option<Vec<String>>,
    /// Updated collection scope.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collections: Option<Option<Vec<String>>>,
    /// Updated description.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    /// Updated active flag.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub active: Option<bool>,
}

/// Paginated list of webhooks.
#[derive(Debug, Clone, Deserialize)]
pub struct WebhookListResponse {
    /// Webhooks in this page.
    pub webhooks: Vec<Webhook>,
    /// Total number of webhooks, when returned by the API.
    pub total: Option<u32>,
}

/// A webhook delivery attempt.
#[derive(Debug, Clone, Deserialize)]
pub struct WebhookDelivery {
    /// Delivery ID.
    pub id: String,
    /// Webhook ID.
    pub webhook_id: String,
    /// Event type.
    pub event: String,
    /// Delivery payload.
    pub payload: serde_json::Value,
    /// Delivery status.
    pub status: String,
    /// Number of delivery attempts.
    pub attempts: u32,
    /// HTTP status code from the last attempt.
    pub last_status_code: Option<u16>,
    /// Error message from the last attempt.
    pub last_error: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Completion timestamp.
    pub completed_at: Option<String>,
}

/// Paginated list of webhook deliveries.
#[derive(Debug, Clone, Deserialize)]
pub struct WebhookDeliveryListResponse {
    /// Deliveries in this page.
    pub deliveries: Vec<WebhookDelivery>,
    /// Total number of deliveries.
    pub total: u32,
}

/// Response from testing a webhook.
#[derive(Debug, Clone, Deserialize)]
pub struct WebhookTestResponse {
    /// Delivery status.
    pub status: String,
    /// HTTP status code from the test delivery.
    pub status_code: Option<u16>,
    /// Error message if the test failed.
    pub error: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_webhook() {
        let json = r#"{"id":"wh-1","url":"https://example.com/hook","events":["document.ready"],"collections":null,"description":"test","active":true,"created_by":null,"created_at":"","updated_at":""}"#;
        let wh: Webhook = serde_json::from_str(json).unwrap();
        assert_eq!(wh.id, "wh-1");
        assert_eq!(wh.events, vec!["document.ready"]);
        assert_eq!(wh.collections, None);
        assert!(wh.active);
    }

    #[test]
    fn test_deserialize_create_webhook_response_with_flatten() {
        let json = r#"{"id":"wh-1","url":"https://example.com","events":["document.ready"],"collections":null,"description":"","active":true,"created_by":null,"created_at":"","updated_at":"","secret":"whsec_abc123"}"#;
        let resp: CreateWebhookResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.secret, "whsec_abc123");
        assert_eq!(resp.webhook.id, "wh-1");
    }

    #[test]
    fn test_deserialize_webhook_test_response() {
        let json = r#"{"status":"ok","status_code":200,"error":null}"#;
        let resp: WebhookTestResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.status_code, Some(200));
        assert_eq!(resp.error, None);
    }

    #[test]
    fn test_deserialize_webhook_list_without_total() {
        let json = r#"{"webhooks":[]}"#;
        let resp: WebhookListResponse = serde_json::from_str(json).unwrap();
        assert!(resp.webhooks.is_empty());
        assert_eq!(resp.total, None);
    }

    #[test]
    fn test_serialize_update_webhook_body_skips_none() {
        let body = UpdateWebhookBody {
            active: Some(false),
            ..Default::default()
        };
        let json = serde_json::to_value(&body).unwrap();
        assert_eq!(json["active"], false);
        assert!(json.get("url").is_none());
    }
}
