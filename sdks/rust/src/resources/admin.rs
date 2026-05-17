use std::collections::VecDeque;
use std::pin::Pin;
use std::task::{Context, Poll};

use futures_core::Stream;

use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::sse::FrameParser;
use crate::types::access::{AccessLogListResponse, AccessLogOverviewResponse};
use crate::types::admin::{
    AdminRealtimeEvent, ApiKey, ApiKeyListResponse, AuditLogListResponse, BackupCreateBody,
    BackupJob, BackupJobListResponse, CreateApiKeyBody, CreateApiKeyResponse,
    CreateEmbeddingPresetBody, CreateMcpServerBody, CreateMcpServerResponse, CreateUserBody,
    EmbeddingPreset, EmbeddingPresetListResponse, InstanceSettingsResponse,
    InstanceSettingsTestResponse, McpServer, McpServerListResponse, ResetInstanceSettingsBody,
    TestInstanceSettingsBody, UpdateApiKeyBody, UpdateEmbeddingPresetBody,
    UpdateInstanceSettingsBody, UpdateMcpServerBody, UpdateUserBody, UserListResponse,
};
use crate::types::auth::User;
use crate::types::common::{PaginationOptions, StatusResponse};
use crate::types::connectors::{GoogleConnectorConfig, UpdateGoogleConnectorConfigBody};

/// Admin resource.
pub struct Admin<'a> {
    pub(crate) client: &'a BigRag,
}

impl Admin<'_> {
    /// Access admin user operations.
    pub fn users(&self) -> AdminUsers<'_> {
        AdminUsers {
            client: self.client,
        }
    }

    /// Access admin API key operations.
    pub fn api_keys(&self) -> AdminApiKeys<'_> {
        AdminApiKeys {
            client: self.client,
        }
    }

    /// Access admin access log operations.
    pub fn access(&self) -> AdminAccess<'_> {
        AdminAccess {
            client: self.client,
        }
    }

    /// Access admin audit log operations.
    pub fn audit(&self) -> AdminAudit<'_> {
        AdminAudit {
            client: self.client,
        }
    }

    /// Access admin backup operations.
    pub fn backups(&self) -> AdminBackups<'_> {
        AdminBackups {
            client: self.client,
        }
    }

    /// Access admin connector config operations.
    pub fn connectors(&self) -> AdminConnectors<'_> {
        AdminConnectors {
            client: self.client,
        }
    }

    /// Access admin embedding preset operations.
    pub fn embedding_presets(&self) -> AdminEmbeddingPresets<'_> {
        AdminEmbeddingPresets {
            client: self.client,
        }
    }

    /// Access admin MCP server operations.
    pub fn mcp_servers(&self) -> AdminMcpServers<'_> {
        AdminMcpServers {
            client: self.client,
        }
    }

    /// Access admin realtime streams.
    pub fn realtime(&self) -> AdminRealtime<'_> {
        AdminRealtime {
            client: self.client,
        }
    }

    /// Access admin runtime settings.
    pub fn settings(&self) -> AdminSettings<'_> {
        AdminSettings {
            client: self.client,
        }
    }
}

/// Admin runtime settings resource.
pub struct AdminSettings<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminSettings<'_> {
    /// List runtime settings.
    pub async fn list(&self) -> Result<InstanceSettingsResponse, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/settings", vec![])
            .await
    }

    /// Update runtime settings.
    pub async fn update(
        &self,
        body: UpdateInstanceSettingsBody,
    ) -> Result<InstanceSettingsResponse, BigRagError> {
        self.client.transport.put("/v1/admin/settings", &body).await
    }

    /// Test runtime settings.
    pub async fn test(
        &self,
        body: Option<TestInstanceSettingsBody>,
    ) -> Result<InstanceSettingsTestResponse, BigRagError> {
        let body = body.unwrap_or_else(|| TestInstanceSettingsBody {
            values: serde_json::json!({}),
        });
        self.client
            .transport
            .post("/v1/admin/settings/test", &body)
            .await
    }

    /// Reset runtime settings.
    pub async fn reset(
        &self,
        body: Option<ResetInstanceSettingsBody>,
    ) -> Result<StatusResponse, BigRagError> {
        let body = body.unwrap_or_else(|| ResetInstanceSettingsBody { keys: vec![] });
        self.client
            .transport
            .post("/v1/admin/settings/reset", &body)
            .await
    }

    /// Purge the embedding model cache.
    pub async fn purge_embedding_cache(&self) -> Result<StatusResponse, BigRagError> {
        self.client
            .transport
            .post(
                "/v1/admin/settings/embedding-cache/purge",
                &serde_json::Value::Null,
            )
            .await
    }
}

/// Admin backups resource.
pub struct AdminBackups<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminBackups<'_> {
    /// List backup jobs.
    pub async fn list(
        &self,
        options: Option<PaginationOptions>,
    ) -> Result<BackupJobListResponse, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/backups", pagination(options))
            .await
    }

    /// Get a backup job.
    pub async fn get(&self, backup_id: &str) -> Result<BackupJob, BigRagError> {
        let path = format!("/v1/admin/backups/{}", urlencode(backup_id));
        self.client.transport.get(&path, vec![]).await
    }

    /// Create a backup job.
    pub async fn create(&self, body: Option<BackupCreateBody>) -> Result<BackupJob, BigRagError> {
        let body = body.unwrap_or_default();
        self.client.transport.post("/v1/admin/backups", &body).await
    }
}

/// Admin users resource.
pub struct AdminUsers<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminUsers<'_> {
    /// List users.
    pub async fn list(
        &self,
        options: Option<PaginationOptions>,
    ) -> Result<UserListResponse, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/users", pagination(options))
            .await
    }

    /// Create a user.
    pub async fn create(&self, body: CreateUserBody) -> Result<User, BigRagError> {
        self.client.transport.post("/v1/admin/users", &body).await
    }

    /// Update a user.
    pub async fn update(&self, user_id: &str, body: UpdateUserBody) -> Result<User, BigRagError> {
        let path = format!("/v1/admin/users/{}", urlencode(user_id));
        self.client.transport.patch(&path, &body).await
    }

    /// Delete a user.
    pub async fn delete(&self, user_id: &str) -> Result<StatusResponse, BigRagError> {
        let path = format!("/v1/admin/users/{}", urlencode(user_id));
        self.client.transport.delete(&path).await
    }
}

/// Admin API keys resource.
pub struct AdminApiKeys<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminApiKeys<'_> {
    /// List API keys.
    pub async fn list(
        &self,
        options: Option<PaginationOptions>,
    ) -> Result<ApiKeyListResponse, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/api-keys", pagination(options))
            .await
    }

    /// Create an API key.
    pub async fn create(
        &self,
        body: CreateApiKeyBody,
    ) -> Result<CreateApiKeyResponse, BigRagError> {
        self.client
            .transport
            .post("/v1/admin/api-keys", &body)
            .await
    }

    /// Update an API key.
    pub async fn update(
        &self,
        key_id: &str,
        body: UpdateApiKeyBody,
    ) -> Result<ApiKey, BigRagError> {
        let path = format!("/v1/admin/api-keys/{}", urlencode(key_id));
        self.client.transport.patch(&path, &body).await
    }

    /// Delete an API key.
    pub async fn delete(&self, key_id: &str) -> Result<StatusResponse, BigRagError> {
        let path = format!("/v1/admin/api-keys/{}", urlencode(key_id));
        self.client.transport.delete(&path).await
    }
}

/// Access log filters.
#[derive(Debug, Clone, Default)]
pub struct AccessLogOptions {
    /// Action filter.
    pub action: Option<String>,
    /// Actor ID filter.
    pub actor_id: Option<String>,
    /// Collection filter.
    pub collection: Option<String>,
    /// HTTP method filter.
    pub method: Option<String>,
    /// Path substring filter.
    pub path: Option<String>,
    /// Status family filter.
    pub status_family: Option<String>,
    /// Success filter.
    pub success: Option<bool>,
    /// Pagination limit.
    pub limit: Option<u32>,
    /// Pagination offset.
    pub offset: Option<u32>,
}

/// Admin access log resource.
pub struct AdminAccess<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminAccess<'_> {
    /// List access log entries.
    pub async fn logs(
        &self,
        options: Option<AccessLogOptions>,
    ) -> Result<AccessLogListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(options) = options {
            push_opt(&mut query, "action", options.action);
            push_opt(&mut query, "actor_id", options.actor_id);
            push_opt(&mut query, "collection", options.collection);
            push_opt(&mut query, "method", options.method);
            push_opt(&mut query, "path", options.path);
            push_opt(&mut query, "status_family", options.status_family);
            if let Some(success) = options.success {
                query.push(("success".to_string(), success.to_string()));
            }
            if let Some(limit) = options.limit {
                query.push(("limit".to_string(), limit.to_string()));
            }
            if let Some(offset) = options.offset {
                query.push(("offset".to_string(), offset.to_string()));
            }
        }
        self.client
            .transport
            .get("/v1/admin/access/logs", query)
            .await
    }

    /// Get access log overview metrics.
    pub async fn overview(
        &self,
        window_days: Option<u32>,
    ) -> Result<AccessLogOverviewResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(window_days) = window_days {
            query.push(("window_days".to_string(), window_days.to_string()));
        }
        self.client
            .transport
            .get("/v1/admin/access/overview", query)
            .await
    }
}

/// Audit log filters.
#[derive(Debug, Clone, Default)]
pub struct AuditLogOptions {
    /// Action filter.
    pub action: Option<String>,
    /// Actor ID filter.
    pub actor_id: Option<String>,
    /// Resource type filter.
    pub resource_type: Option<String>,
    /// Pagination limit.
    pub limit: Option<u32>,
    /// Pagination offset.
    pub offset: Option<u32>,
}

/// Admin audit log resource.
pub struct AdminAudit<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminAudit<'_> {
    /// List audit log entries.
    pub async fn list(
        &self,
        options: Option<AuditLogOptions>,
    ) -> Result<AuditLogListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(options) = options {
            push_opt(&mut query, "action", options.action);
            push_opt(&mut query, "actor_id", options.actor_id);
            push_opt(&mut query, "resource_type", options.resource_type);
            if let Some(limit) = options.limit {
                query.push(("limit".to_string(), limit.to_string()));
            }
            if let Some(offset) = options.offset {
                query.push(("offset".to_string(), offset.to_string()));
            }
        }
        self.client.transport.get("/v1/admin/audit", query).await
    }
}

/// Admin connectors resource.
pub struct AdminConnectors<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminConnectors<'_> {
    /// Access Google connector config.
    pub fn google(&self) -> AdminGoogleConnector<'_> {
        AdminGoogleConnector {
            client: self.client,
        }
    }
}

/// Admin Google connector config resource.
pub struct AdminGoogleConnector<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminGoogleConnector<'_> {
    /// Get Google connector config.
    pub async fn get(&self) -> Result<GoogleConnectorConfig, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/connectors/google", vec![])
            .await
    }

    /// Update Google connector config.
    pub async fn update(
        &self,
        body: UpdateGoogleConnectorConfigBody,
    ) -> Result<GoogleConnectorConfig, BigRagError> {
        self.client
            .transport
            .put("/v1/admin/connectors/google", &body)
            .await
    }
}

/// Admin embedding presets resource.
pub struct AdminEmbeddingPresets<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminEmbeddingPresets<'_> {
    /// List embedding presets.
    pub async fn list(
        &self,
        options: Option<PaginationOptions>,
    ) -> Result<EmbeddingPresetListResponse, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/embedding-presets", pagination(options))
            .await
    }

    /// Create an embedding preset.
    pub async fn create(
        &self,
        body: CreateEmbeddingPresetBody,
    ) -> Result<EmbeddingPreset, BigRagError> {
        self.client
            .transport
            .post("/v1/admin/embedding-presets", &body)
            .await
    }

    /// Update an embedding preset.
    pub async fn update(
        &self,
        preset_id: &str,
        body: UpdateEmbeddingPresetBody,
    ) -> Result<EmbeddingPreset, BigRagError> {
        let path = format!("/v1/admin/embedding-presets/{}", urlencode(preset_id));
        self.client.transport.patch(&path, &body).await
    }

    /// Delete an embedding preset.
    pub async fn delete(&self, preset_id: &str) -> Result<StatusResponse, BigRagError> {
        let path = format!("/v1/admin/embedding-presets/{}", urlencode(preset_id));
        self.client.transport.delete(&path).await
    }
}

/// Admin MCP servers resource.
pub struct AdminMcpServers<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminMcpServers<'_> {
    /// List MCP servers.
    pub async fn list(&self) -> Result<McpServerListResponse, BigRagError> {
        self.client
            .transport
            .get("/v1/admin/mcp-servers", vec![])
            .await
    }

    /// Create an MCP server.
    pub async fn create(
        &self,
        body: CreateMcpServerBody,
    ) -> Result<CreateMcpServerResponse, BigRagError> {
        self.client
            .transport
            .post("/v1/admin/mcp-servers", &body)
            .await
    }

    /// Update an MCP server.
    pub async fn update(
        &self,
        server_id: &str,
        body: UpdateMcpServerBody,
    ) -> Result<McpServer, BigRagError> {
        let path = format!("/v1/admin/mcp-servers/{}", urlencode(server_id));
        self.client.transport.patch(&path, &body).await
    }

    /// Rotate an MCP server key.
    pub async fn rotate(&self, server_id: &str) -> Result<CreateMcpServerResponse, BigRagError> {
        let path = format!("/v1/admin/mcp-servers/{}/rotate", urlencode(server_id));
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Delete an MCP server.
    pub async fn delete(&self, server_id: &str) -> Result<StatusResponse, BigRagError> {
        let path = format!("/v1/admin/mcp-servers/{}", urlencode(server_id));
        self.client.transport.delete(&path).await
    }
}

/// Admin realtime document filters.
#[derive(Debug, Clone, Default)]
pub struct AdminRealtimeDocumentsOptions {
    /// Search filename, type, ID, or error text.
    pub q: Option<String>,
    /// Document status filter.
    pub status: Option<String>,
    /// Sort field.
    pub sort: Option<String>,
    /// Sort order.
    pub order: Option<String>,
    /// Pagination limit.
    pub limit: Option<u32>,
    /// Pagination offset.
    pub offset: Option<u32>,
}

/// Admin realtime connector sync job filters.
#[derive(Debug, Clone, Default)]
pub struct AdminRealtimeConnectorSyncJobsOptions {
    /// Collection filter.
    pub collection: Option<String>,
    /// Source ID filter.
    pub source_id: Option<String>,
    /// Result limit.
    pub limit: Option<u32>,
}

/// Admin realtime SSE resource.
pub struct AdminRealtime<'a> {
    pub(crate) client: &'a BigRag,
}

impl AdminRealtime<'_> {
    /// Stream collection documents.
    pub async fn documents(
        &self,
        collection: &str,
        options: Option<AdminRealtimeDocumentsOptions>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        if let Some(options) = options {
            push_opt(&mut query, "q", options.q);
            push_opt(&mut query, "status", options.status);
            push_opt(&mut query, "sort", options.sort);
            push_opt(&mut query, "order", options.order);
            push_opt_u32(&mut query, "limit", options.limit);
            push_opt_u32(&mut query, "offset", options.offset);
        }
        self.stream(
            &format!(
                "/v1/admin/realtime/collections/{}/documents",
                urlencode(collection)
            ),
            query,
        )
        .await
    }

    /// Stream batch document status.
    pub async fn document_batch_status<S: AsRef<str>>(
        &self,
        collection: &str,
        document_ids: &[S],
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let document_ids = document_ids
            .iter()
            .map(|id| id.as_ref())
            .collect::<Vec<_>>()
            .join(",");
        self.stream(
            &format!(
                "/v1/admin/realtime/collections/{}/documents/batch-status",
                urlencode(collection)
            ),
            vec![("document_ids".to_string(), document_ids)],
        )
        .await
    }

    /// Stream one document.
    pub async fn document(
        &self,
        collection: &str,
        document_id: &str,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream(
            &format!(
                "/v1/admin/realtime/collections/{}/documents/{}",
                urlencode(collection),
                urlencode(document_id)
            ),
            vec![],
        )
        .await
    }

    /// Stream one upload session.
    pub async fn upload_session(
        &self,
        collection: &str,
        session_id: &str,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream(
            &format!(
                "/v1/admin/realtime/collections/{}/upload-sessions/{}",
                urlencode(collection),
                urlencode(session_id)
            ),
            vec![],
        )
        .await
    }

    /// Stream collection stats.
    pub async fn collection_stats(
        &self,
        collection: &str,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream(
            &format!(
                "/v1/admin/realtime/collections/{}/stats",
                urlencode(collection)
            ),
            vec![],
        )
        .await
    }

    /// Stream connector sources.
    pub async fn connector_sources(
        &self,
        provider: &str,
        collection: Option<&str>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        push_opt_ref(&mut query, "collection", collection);
        self.stream(
            &format!("/v1/admin/realtime/{}/sources", urlencode(provider)),
            query,
        )
        .await
    }

    /// Stream connector sync jobs.
    pub async fn connector_sync_jobs(
        &self,
        provider: &str,
        options: Option<AdminRealtimeConnectorSyncJobsOptions>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        if let Some(options) = options {
            push_opt(&mut query, "collection", options.collection);
            push_opt(&mut query, "source_id", options.source_id);
            push_opt_u32(&mut query, "limit", options.limit);
        }
        self.stream(
            &format!("/v1/admin/realtime/{}/sync-jobs", urlencode(provider)),
            query,
        )
        .await
    }

    /// Stream backup jobs.
    pub async fn backups(
        &self,
        options: Option<PaginationOptions>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream("/v1/admin/realtime/backups", pagination(options))
            .await
    }

    /// Stream access log overview.
    pub async fn access_overview(
        &self,
        window_days: Option<u32>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        push_opt_u32(&mut query, "window_days", window_days);
        self.stream("/v1/admin/realtime/access/overview", query)
            .await
    }

    /// Stream access logs.
    pub async fn access_logs(
        &self,
        options: Option<AccessLogOptions>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        if let Some(options) = options {
            push_opt(&mut query, "action", options.action);
            push_opt(&mut query, "actor_id", options.actor_id);
            push_opt(&mut query, "collection", options.collection);
            push_opt(&mut query, "method", options.method);
            push_opt(&mut query, "path", options.path);
            push_opt(&mut query, "status_family", options.status_family);
            if let Some(success) = options.success {
                query.push(("success".to_string(), success.to_string()));
            }
            push_opt_u32(&mut query, "limit", options.limit);
            push_opt_u32(&mut query, "offset", options.offset);
        }
        self.stream("/v1/admin/realtime/access/logs", query).await
    }

    /// Stream audit logs.
    pub async fn audit(
        &self,
        options: Option<AuditLogOptions>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        if let Some(options) = options {
            push_opt(&mut query, "action", options.action);
            push_opt(&mut query, "actor_id", options.actor_id);
            push_opt(&mut query, "resource_type", options.resource_type);
            push_opt_u32(&mut query, "limit", options.limit);
            push_opt_u32(&mut query, "offset", options.offset);
        }
        self.stream("/v1/admin/realtime/audit", query).await
    }

    /// Stream usage stats.
    pub async fn usage(
        &self,
        window_days: Option<u32>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let mut query = Vec::new();
        push_opt_u32(&mut query, "window_days", window_days);
        self.stream("/v1/admin/realtime/usage", query).await
    }

    /// Stream platform stats.
    pub async fn platform_stats(&self) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream("/v1/admin/realtime/platform/stats", vec![])
            .await
    }

    /// Stream platform readiness.
    pub async fn platform_readiness(&self) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream("/v1/admin/realtime/platform/readiness", vec![])
            .await
    }

    /// Stream a custom admin realtime path.
    pub async fn custom(
        &self,
        path: &str,
        query: Vec<(String, String)>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        self.stream(path, query).await
    }

    async fn stream(
        &self,
        path: &str,
        query: Vec<(String, String)>,
    ) -> Result<AdminRealtimeStream, BigRagError> {
        let path = stream_path(path, query);
        let response = self.client.transport.get_stream(&path).await?;
        Ok(AdminRealtimeStream::new(response))
    }
}

/// A stream of admin realtime Server-Sent Events.
pub struct AdminRealtimeStream {
    inner: Pin<Box<dyn Stream<Item = Result<bytes::Bytes, reqwest::Error>> + Send>>,
    parser: FrameParser,
    pending: VecDeque<Result<AdminRealtimeEvent, BigRagError>>,
}

impl AdminRealtimeStream {
    pub(crate) fn new(response: reqwest::Response) -> Self {
        Self {
            inner: Box::pin(response.bytes_stream()),
            parser: FrameParser::new(),
            pending: VecDeque::new(),
        }
    }
}

impl Stream for AdminRealtimeStream {
    type Item = Result<AdminRealtimeEvent, BigRagError>;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        if let Some(event) = self.pending.pop_front() {
            return Poll::Ready(Some(event));
        }

        match self.inner.as_mut().poll_next(cx) {
            Poll::Ready(Some(Ok(chunk))) => {
                let text = String::from_utf8_lossy(&chunk);
                self.pending = self
                    .parser
                    .push(&text)
                    .into_iter()
                    .map(|frame| {
                        serde_json::from_str(&frame.data)
                            .map(|data| AdminRealtimeEvent {
                                event: frame.event,
                                data,
                            })
                            .map_err(BigRagError::from)
                    })
                    .collect();

                if let Some(event) = self.pending.pop_front() {
                    Poll::Ready(Some(event))
                } else {
                    cx.waker().wake_by_ref();
                    Poll::Pending
                }
            }
            Poll::Ready(Some(Err(e))) => {
                Poll::Ready(Some(Err(BigRagError::Connection(e.to_string()))))
            }
            Poll::Ready(None) => Poll::Ready(None),
            Poll::Pending => Poll::Pending,
        }
    }
}

fn pagination(options: Option<PaginationOptions>) -> Vec<(String, String)> {
    let mut query = Vec::new();
    if let Some(options) = options {
        if let Some(limit) = options.limit {
            query.push(("limit".to_string(), limit.to_string()));
        }
        if let Some(offset) = options.offset {
            query.push(("offset".to_string(), offset.to_string()));
        }
    }
    query
}

fn push_opt(query: &mut Vec<(String, String)>, key: &str, value: Option<String>) {
    if let Some(value) = value {
        query.push((key.to_string(), value));
    }
}

fn push_opt_ref(query: &mut Vec<(String, String)>, key: &str, value: Option<&str>) {
    if let Some(value) = value {
        query.push((key.to_string(), value.to_string()));
    }
}

fn push_opt_u32(query: &mut Vec<(String, String)>, key: &str, value: Option<u32>) {
    if let Some(value) = value {
        query.push((key.to_string(), value.to_string()));
    }
}

fn stream_path(path: &str, query: Vec<(String, String)>) -> String {
    if query.is_empty() {
        return path.to_string();
    }
    let query = query
        .into_iter()
        .map(|(key, value)| format!("{}={}", urlencode(&key), urlencode(&value)))
        .collect::<Vec<_>>()
        .join("&");
    format!("{}?{}", path, query)
}
