use serde::{Deserialize, Serialize};

use crate::types::auth::User;

/// User list response.
#[derive(Debug, Clone, Deserialize)]
pub struct UserListResponse {
    /// Users.
    pub users: Vec<User>,
    /// Total user count.
    pub total: u32,
}

/// Body for creating a user.
#[derive(Debug, Clone, Serialize)]
pub struct CreateUserBody {
    /// Email address.
    pub email: String,
    /// Password.
    pub password: String,
    /// Display name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display_name: Option<String>,
    /// Role.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
}

/// Body for updating a user.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateUserBody {
    /// Display name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display_name: Option<String>,
    /// Role.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    /// Password.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub password: Option<String>,
}

/// API key metadata.
#[derive(Debug, Clone, Deserialize)]
pub struct ApiKey {
    /// API key ID.
    pub id: String,
    /// API key name.
    pub name: String,
    /// Key prefix.
    pub prefix: String,
    /// Whether the key is active.
    pub active: bool,
    /// Granted scopes.
    pub scopes: Vec<String>,
    /// Collection pin.
    pub collection: Option<String>,
    /// Last used timestamp.
    pub last_used_at: Option<String>,
    /// Expiry timestamp.
    pub expires_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Body for creating an API key.
#[derive(Debug, Clone, Serialize)]
pub struct CreateApiKeyBody {
    /// API key name.
    pub name: String,
    /// Expiry timestamp.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<String>,
    /// Granted scopes.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scopes: Option<Vec<String>>,
    /// Collection pin.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collection: Option<String>,
}

/// API key creation response.
#[derive(Debug, Clone, Deserialize)]
pub struct CreateApiKeyResponse {
    /// API key ID.
    pub id: String,
    /// API key name.
    pub name: String,
    /// Key prefix.
    pub prefix: String,
    /// Whether the key is active.
    pub active: bool,
    /// Granted scopes.
    pub scopes: Vec<String>,
    /// Collection pin.
    pub collection: Option<String>,
    /// Last used timestamp.
    pub last_used_at: Option<String>,
    /// Expiry timestamp.
    pub expires_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
    /// Plaintext key.
    pub key: String,
}

/// Body for updating an API key.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateApiKeyBody {
    /// API key name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// Active flag.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub active: Option<bool>,
    /// Granted scopes.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scopes: Option<Vec<String>>,
    /// Collection pin.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collection: Option<String>,
}

/// API key list response.
#[derive(Debug, Clone, Deserialize)]
pub struct ApiKeyListResponse {
    /// API keys.
    pub keys: Vec<ApiKey>,
    /// Total key count.
    pub total: u32,
}

/// Audit log entry.
#[derive(Debug, Clone, Deserialize)]
pub struct AuditLogEntry {
    /// Entry ID.
    pub id: String,
    /// Actor user ID.
    pub actor_id: Option<String>,
    /// Actor email.
    pub actor_email: Option<String>,
    /// API key ID.
    pub api_key_id: Option<String>,
    /// Action.
    pub action: String,
    /// Resource type.
    pub resource_type: String,
    /// Resource ID.
    pub resource_id: Option<String>,
    /// Metadata.
    pub metadata: serde_json::Value,
    /// Client IP.
    pub ip: Option<String>,
    /// User agent.
    pub user_agent: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
}

/// Audit log list response.
#[derive(Debug, Clone, Deserialize)]
pub struct AuditLogListResponse {
    /// Entries.
    pub entries: Vec<AuditLogEntry>,
    /// Total entry count.
    pub total: u32,
}

/// Embedding preset.
#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingPreset {
    /// Preset ID.
    pub id: String,
    /// Preset name.
    pub name: String,
    /// Provider.
    pub provider: String,
    /// Model.
    pub model: String,
    /// OpenAI-compatible base URL.
    pub base_url: Option<String>,
    /// Embedding dimension.
    pub dimension: u32,
    /// Whether an API key is stored.
    pub has_api_key: bool,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Body for creating an embedding preset.
#[derive(Debug, Clone, Serialize)]
pub struct CreateEmbeddingPresetBody {
    /// Preset name.
    pub name: String,
    /// Provider.
    pub provider: String,
    /// Model.
    pub model: String,
    /// API key.
    pub api_key: String,
    /// OpenAI-compatible base URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    /// Embedding dimension.
    pub dimension: u32,
}

/// Body for updating an embedding preset.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateEmbeddingPresetBody {
    /// Preset name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// Provider.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider: Option<String>,
    /// Model.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// API key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    /// OpenAI-compatible base URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    /// Embedding dimension.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimension: Option<u32>,
}

/// Embedding preset list response.
#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingPresetListResponse {
    /// Presets.
    pub presets: Vec<EmbeddingPreset>,
    /// Total preset count.
    pub total: u32,
}

/// MCP server config.
#[derive(Debug, Clone, Deserialize)]
pub struct McpServer {
    /// Server ID.
    pub id: String,
    /// Display title.
    pub title: String,
    /// MCP server name.
    pub server_name: String,
    /// Collection pin.
    pub collection: Option<String>,
    /// API key prefix.
    pub key_prefix: String,
    /// Whether the key is active.
    pub key_active: bool,
    /// Last used timestamp.
    pub last_used_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Body for creating an MCP server.
#[derive(Debug, Clone, Serialize)]
pub struct CreateMcpServerBody {
    /// Display title.
    pub title: String,
    /// MCP server name.
    pub server_name: String,
    /// Collection pin.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collection: Option<String>,
}

/// Body for updating an MCP server.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateMcpServerBody {
    /// Display title.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// MCP server name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub server_name: Option<String>,
    /// Collection pin.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collection: Option<String>,
}

/// MCP server creation response.
#[derive(Debug, Clone, Deserialize)]
pub struct CreateMcpServerResponse {
    /// Server ID.
    pub id: String,
    /// Display title.
    pub title: String,
    /// MCP server name.
    pub server_name: String,
    /// Collection pin.
    pub collection: Option<String>,
    /// API key prefix.
    pub key_prefix: String,
    /// Whether the key is active.
    pub key_active: bool,
    /// Last used timestamp.
    pub last_used_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
    /// Plaintext API key.
    pub api_key: String,
}

/// MCP server list response.
#[derive(Debug, Clone, Deserialize)]
pub struct McpServerListResponse {
    /// Servers.
    pub servers: Vec<McpServer>,
    /// Total server count.
    pub total: u32,
}

/// Instance setting registry entry.
#[derive(Debug, Clone, Deserialize)]
pub struct InstanceSettingSpec {
    /// Setting key.
    pub key: String,
    /// Setting group.
    pub group: String,
    /// Display label.
    pub label: String,
    /// Display description.
    pub description: String,
    /// Setting value kind.
    pub kind: String,
    /// Redacted default value.
    pub default: serde_json::Value,
    /// Allowed options for select settings.
    pub options: Vec<String>,
    /// Minimum numeric value.
    pub min: Option<f64>,
    /// Maximum numeric value.
    pub max: Option<f64>,
    /// Whether the setting is secret.
    pub secret: bool,
}

/// Public instance setting value.
#[derive(Debug, Clone, Deserialize)]
pub struct InstanceSetting {
    /// Setting key.
    pub key: String,
    /// Public setting value.
    pub value: serde_json::Value,
    /// Whether a value is configured.
    pub has_value: bool,
    /// Value source.
    pub source: String,
    /// Last update timestamp.
    pub updated_at: Option<String>,
    /// Last updater ID.
    pub updated_by: Option<String>,
}

/// Response from listing instance settings.
#[derive(Debug, Clone, Deserialize)]
pub struct InstanceSettingsResponse {
    /// Setting registry.
    pub specs: Vec<InstanceSettingSpec>,
    /// Current public values keyed by setting name.
    pub values: std::collections::BTreeMap<String, InstanceSetting>,
}

/// Body for updating instance settings.
#[derive(Debug, Clone, Serialize)]
pub struct UpdateInstanceSettingsBody {
    /// Setting values keyed by setting name.
    pub values: serde_json::Value,
}

/// Body for resetting instance settings.
#[derive(Debug, Clone, Serialize)]
pub struct ResetInstanceSettingsBody {
    /// Keys to reset. Empty resets all UI-managed settings.
    pub keys: Vec<String>,
}

/// Body for validating instance settings.
#[derive(Debug, Clone, Serialize)]
pub struct TestInstanceSettingsBody {
    /// Setting values keyed by setting name.
    pub values: serde_json::Value,
}

/// Response from validating instance settings.
#[derive(Debug, Clone, Deserialize)]
pub struct InstanceSettingsTestResponse {
    /// Validation status.
    pub status: String,
    /// Checked setting keys.
    pub checked: Vec<String>,
    /// Validation message.
    pub message: String,
}

/// Body for creating a backup job.
#[derive(Debug, Clone, Default, Serialize)]
pub struct BackupCreateBody {
    /// Backup label.
    pub label: String,
}

/// Backup job response.
#[derive(Debug, Clone, Deserialize)]
pub struct BackupJob {
    /// Backup job ID.
    pub id: String,
    /// Backup label.
    pub label: String,
    /// Job status.
    pub status: String,
    /// Progress fraction.
    pub progress: f64,
    /// Destination prefix.
    pub destination_prefix: String,
    /// Exported object count.
    pub object_count: u64,
    /// Exported byte count.
    pub byte_count: u64,
    /// Backup manifest summary.
    pub manifest: serde_json::Value,
    /// Failure message.
    pub error_message: Option<String>,
    /// Creator user ID.
    pub created_by: Option<String>,
    /// Start timestamp.
    pub started_at: Option<String>,
    /// Completion timestamp.
    pub completed_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Backup job list response.
#[derive(Debug, Clone, Deserialize)]
pub struct BackupJobListResponse {
    /// Backup jobs.
    pub jobs: Vec<BackupJob>,
    /// Total matching jobs.
    pub total: u32,
}

/// Admin realtime SSE event.
#[derive(Debug, Clone, Deserialize)]
pub struct AdminRealtimeEvent {
    /// SSE event name.
    pub event: String,
    /// Parsed event data.
    pub data: serde_json::Value,
}
