use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::types::common::{PaginationOptions, StatusResponse};
use crate::types::webhooks::{
    CreateWebhookBody, CreateWebhookResponse, UpdateWebhookBody, Webhook,
    WebhookDeliveryListResponse, WebhookListResponse, WebhookTestResponse,
};

/// Webhooks resource — manage webhook subscriptions.
pub struct Webhooks<'a> {
    pub(crate) client: &'a BigRag,
}

impl Webhooks<'_> {
    /// Create a new webhook.
    pub async fn create(
        &self,
        body: CreateWebhookBody,
    ) -> Result<CreateWebhookResponse, BigRagError> {
        self.client
            .transport
            .post("/v1/admin/webhooks", &body)
            .await
    }

    /// List all webhooks.
    pub async fn list(&self) -> Result<WebhookListResponse, BigRagError> {
        self.list_with_options(None).await
    }

    /// List webhooks with pagination options.
    pub async fn list_with_options(
        &self,
        options: Option<PaginationOptions>,
    ) -> Result<WebhookListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(opts) = options {
            if let Some(limit) = opts.limit {
                query.push(("limit".into(), limit.to_string()));
            }
            if let Some(offset) = opts.offset {
                query.push(("offset".into(), offset.to_string()));
            }
        }
        self.client.transport.get("/v1/admin/webhooks", query).await
    }

    /// Get a webhook by ID.
    pub async fn get(&self, id: &str) -> Result<Webhook, BigRagError> {
        let path = format!("/v1/admin/webhooks/{}", urlencode(id));
        self.client.transport.get(&path, vec![]).await
    }

    /// Update a webhook.
    pub async fn update(&self, id: &str, body: UpdateWebhookBody) -> Result<Webhook, BigRagError> {
        let path = format!("/v1/admin/webhooks/{}", urlencode(id));
        self.client.transport.put(&path, &body).await
    }

    /// Delete a webhook.
    pub async fn delete(&self, id: &str) -> Result<StatusResponse, BigRagError> {
        let path = format!("/v1/admin/webhooks/{}", urlencode(id));
        self.client.transport.delete(&path).await
    }

    /// List delivery attempts for a webhook.
    pub async fn list_deliveries(
        &self,
        id: &str,
        options: Option<PaginationOptions>,
    ) -> Result<WebhookDeliveryListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(opts) = options {
            if let Some(limit) = opts.limit {
                query.push(("limit".into(), limit.to_string()));
            }
            if let Some(offset) = opts.offset {
                query.push(("offset".into(), offset.to_string()));
            }
        }
        let path = format!("/v1/admin/webhooks/{}/deliveries", urlencode(id));
        self.client.transport.get(&path, query).await
    }

    /// Send a test delivery to a webhook.
    pub async fn test(&self, id: &str) -> Result<WebhookTestResponse, BigRagError> {
        let path = format!("/v1/admin/webhooks/{}/test", urlencode(id));
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Replay a previous webhook delivery.
    pub async fn replay_delivery(
        &self,
        id: &str,
        delivery_id: &str,
    ) -> Result<WebhookTestResponse, BigRagError> {
        let path = format!(
            "/v1/admin/webhooks/{}/deliveries/{}/replay",
            urlencode(id),
            urlencode(delivery_id)
        );
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }
}
