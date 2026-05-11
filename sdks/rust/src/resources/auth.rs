use crate::client::RagComputer;
use crate::error::RagComputerError;
use crate::types::auth::{
    ChangePasswordBody, LoginBody, PreferencesResponse, SessionResponse, SetupBody,
    SetupStatusResponse, UpdatePreferencesBody, WhoamiResponse,
};
use crate::types::common::StatusResponse;

/// Auth resource.
pub struct Auth<'a> {
    pub(crate) client: &'a RagComputer,
}

impl Auth<'_> {
    /// Get first-admin setup status.
    pub async fn setup_status(&self) -> Result<SetupStatusResponse, RagComputerError> {
        self.client
            .transport
            .get("/v1/auth/setup-status", vec![])
            .await
    }

    /// Create the first admin and session.
    pub async fn setup(&self, body: SetupBody) -> Result<SessionResponse, RagComputerError> {
        self.client.transport.post("/v1/auth/setup", &body).await
    }

    /// Create a session.
    pub async fn login(&self, body: LoginBody) -> Result<SessionResponse, RagComputerError> {
        self.client.transport.post("/v1/auth/login", &body).await
    }

    /// End the current session.
    pub async fn logout(&self) -> Result<StatusResponse, RagComputerError> {
        self.client
            .transport
            .post("/v1/auth/logout", &serde_json::Value::Null)
            .await
    }

    /// End all sessions for the current user.
    pub async fn logout_all(&self) -> Result<StatusResponse, RagComputerError> {
        self.client
            .transport
            .post("/v1/auth/logout-all", &serde_json::Value::Null)
            .await
    }

    /// Get current session user.
    pub async fn me(&self) -> Result<SessionResponse, RagComputerError> {
        self.client.transport.get("/v1/auth/me", vec![]).await
    }

    /// Get current auth principal.
    pub async fn whoami(&self) -> Result<WhoamiResponse, RagComputerError> {
        self.client.transport.get("/v1/auth/whoami", vec![]).await
    }

    /// Change current user password.
    pub async fn change_password(
        &self,
        body: ChangePasswordBody,
    ) -> Result<StatusResponse, RagComputerError> {
        self.client.transport.post("/v1/auth/password", &body).await
    }

    /// Get current user preferences.
    pub async fn preferences(&self) -> Result<PreferencesResponse, RagComputerError> {
        self.client
            .transport
            .get("/v1/auth/preferences", vec![])
            .await
    }

    /// Update current user preferences.
    pub async fn update_preferences(
        &self,
        body: UpdatePreferencesBody,
    ) -> Result<PreferencesResponse, RagComputerError> {
        self.client
            .transport
            .put("/v1/auth/preferences", &body)
            .await
    }
}
