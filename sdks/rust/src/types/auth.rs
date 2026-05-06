use serde::{Deserialize, Serialize};

/// Response from setup status checks.
#[derive(Debug, Clone, Deserialize)]
pub struct SetupStatusResponse {
    /// Whether first-admin setup is still required.
    pub needs_setup: bool,
}

/// Body for login.
#[derive(Debug, Clone, Serialize)]
pub struct LoginBody {
    /// User email.
    pub email: String,
    /// User password.
    pub password: String,
}

/// Body for first-admin setup.
#[derive(Debug, Clone, Serialize)]
pub struct SetupBody {
    /// Admin email.
    pub email: String,
    /// Admin password.
    pub password: String,
    /// Display name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display_name: Option<String>,
}

/// Body for password changes.
#[derive(Debug, Clone, Serialize)]
pub struct ChangePasswordBody {
    /// Current password.
    pub current_password: String,
    /// New password.
    pub new_password: String,
}

/// Admin UI user.
#[derive(Debug, Clone, Deserialize)]
pub struct User {
    /// User ID.
    pub id: String,
    /// Email address.
    pub email: String,
    /// Display name.
    pub display_name: String,
    /// User role.
    pub role: String,
    /// Last login timestamp.
    pub last_login_at: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Session response.
#[derive(Debug, Clone, Deserialize)]
pub struct SessionResponse {
    /// Authenticated user.
    pub user: User,
}

/// Current principal response.
#[derive(Debug, Clone, Deserialize)]
pub struct WhoamiResponse {
    /// Whether the request is authenticated.
    pub authenticated: bool,
    /// Authentication method.
    pub auth_method: String,
    /// User ID.
    pub user_id: String,
    /// User email.
    pub user_email: String,
    /// API key ID when authenticated via key.
    pub api_key_id: Option<String>,
    /// API key name when authenticated via key.
    pub api_key_name: Option<String>,
    /// Granted scopes.
    pub scopes: Option<Vec<String>>,
    /// Collection pin when present.
    pub collection: Option<String>,
}

/// Preferences response.
#[derive(Debug, Clone, Deserialize)]
pub struct PreferencesResponse {
    /// Public preference data.
    pub data: serde_json::Value,
}

/// Preferences update body.
#[derive(Debug, Clone, Serialize)]
pub struct UpdatePreferencesBody {
    /// Preference data.
    pub data: serde_json::Value,
}
