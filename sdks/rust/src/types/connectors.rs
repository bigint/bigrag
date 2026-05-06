use serde::{Deserialize, Serialize};

/// Google connector config.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleConnectorConfig {
    /// Provider name.
    pub provider: String,
    /// Whether OAuth credentials are configured.
    pub configured: bool,
    /// Whether the connector is enabled.
    pub enabled: bool,
    /// OAuth client ID.
    pub client_id: String,
    /// Whether a client secret is stored.
    pub has_client_secret: bool,
    /// OAuth callback URL.
    pub callback_url: String,
    /// Creation timestamp.
    pub created_at: Option<String>,
    /// Last update timestamp.
    pub updated_at: Option<String>,
}

/// Body for updating Google connector config.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateGoogleConnectorConfigBody {
    /// Enabled flag.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enabled: Option<bool>,
    /// OAuth client ID.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub client_id: Option<String>,
    /// OAuth client secret.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub client_secret: Option<String>,
}

/// Google account status.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleAccount {
    /// Provider name.
    pub provider: String,
    /// Whether connector config exists.
    pub configured: bool,
    /// Whether the current user is connected.
    pub connected: bool,
    /// Account status.
    pub status: Option<String>,
    /// Connected account email.
    pub email: Option<String>,
    /// Granted scopes.
    pub scopes: Vec<String>,
    /// Token expiry timestamp.
    pub token_expires_at: Option<String>,
    /// Last connection timestamp.
    pub last_connected_at: Option<String>,
}

/// Google Drive file.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleDriveFile {
    /// File ID.
    pub id: String,
    /// File name.
    pub name: String,
    /// MIME type.
    pub mime_type: String,
    /// Source type.
    pub source_type: String,
    /// Modified timestamp.
    pub modified_time: Option<String>,
    /// File size in bytes.
    pub size: Option<u64>,
    /// Web URL.
    pub web_url: Option<String>,
    /// Whether sync is supported.
    pub sync_supported: bool,
    /// Unsupported reason.
    pub unsupported_reason: Option<String>,
}

/// Google Drive file list response.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleDriveFileListResponse {
    /// Provider name.
    pub provider: String,
    /// Parent ID.
    pub parent_id: String,
    /// Search query.
    pub query: String,
    /// Files.
    pub files: Vec<GoogleDriveFile>,
    /// Next page token.
    pub next_page_token: Option<String>,
}

/// Google OAuth start URL response.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleOAuthStartUrlResponse {
    /// Authorization URL.
    pub auth_url: String,
}

/// Body for creating a Google Drive source.
#[derive(Debug, Clone, Serialize)]
pub struct CreateGoogleSourceBody {
    /// Target collection.
    pub collection_name: String,
    /// Drive root ID.
    pub root_id: String,
    /// Drive root name.
    pub root_name: String,
    /// Drive root MIME type.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub root_mime_type: Option<String>,
    /// Source type.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_type: Option<String>,
    /// Source metadata.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

/// Body for updating a Google Drive source.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateGoogleSourceBody {
    /// Whether scheduled sync is enabled.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub schedule_enabled: Option<bool>,
    /// Sync interval in hours.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sync_interval_hours: Option<u32>,
}

/// Google Drive sync source.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleSource {
    /// Source ID.
    pub id: String,
    /// Provider name.
    pub provider: String,
    /// Target collection.
    pub collection_name: String,
    /// Drive root ID.
    pub root_id: String,
    /// Drive root name.
    pub root_name: String,
    /// Drive root MIME type.
    pub root_mime_type: String,
    /// Source type.
    pub source_type: String,
    /// Source status.
    pub status: String,
    /// Whether scheduled sync is enabled.
    pub schedule_enabled: bool,
    /// Sync interval in hours.
    pub sync_interval_hours: u32,
    /// Last sync timestamp.
    pub last_sync_at: Option<String>,
    /// Next sync timestamp.
    pub next_sync_at: Option<String>,
    /// Last sync error.
    pub last_error: Option<String>,
    /// Connected account email.
    pub account_email: Option<String>,
    /// Source metadata.
    pub metadata: serde_json::Value,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Google source list response.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleSourceListResponse {
    /// Sources.
    pub sources: Vec<GoogleSource>,
    /// Total source count.
    pub total: u32,
}

/// Google sync job.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleSyncJob {
    /// Job ID.
    pub id: String,
    /// Provider name.
    pub provider: String,
    /// Source ID.
    pub source_id: Option<String>,
    /// Sync trigger.
    pub trigger: String,
    /// Job status.
    pub status: String,
    /// Total files found.
    pub total_found: u32,
    /// Total documents created.
    pub total_created: u32,
    /// Total documents updated.
    pub total_updated: u32,
    /// Total files skipped.
    pub total_skipped: u32,
    /// Total documents deleted.
    pub total_deleted: u32,
    /// Total files failed.
    pub total_failed: u32,
    /// Error message.
    pub error_message: Option<String>,
    /// Job details.
    pub details: serde_json::Value,
    /// Start timestamp.
    pub started_at: Option<String>,
    /// Completion timestamp.
    pub completed_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Google sync job list response.
#[derive(Debug, Clone, Deserialize)]
pub struct GoogleSyncJobListResponse {
    /// Jobs.
    pub jobs: Vec<GoogleSyncJob>,
    /// Total job count.
    pub total: u32,
}
