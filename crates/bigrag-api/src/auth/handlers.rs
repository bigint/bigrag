use axum::{
    extract::{Extension, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use tracing::{info, warn};

use super::password::{hash_password, verify_password};
use super::session::{
    create_session, create_user, find_user_by_email, has_users, revoke_session, User,
};
use crate::state::AppState;

// -- Request types --

#[derive(Debug, Deserialize)]
pub struct SetupRequest {
    pub email: String,
    pub password: String,
    pub display_name: String,
}

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Deserialize)]
pub struct SignupRequest {
    pub email: String,
    pub password: String,
    pub display_name: String,
    pub invite_code: String,
}

#[derive(Debug, Deserialize)]
pub struct ChangePasswordRequest {
    pub current_password: String,
    pub new_password: String,
}

// -- Helpers --

pub fn error_response(
    status: StatusCode,
    code: &str,
    message: &str,
) -> (StatusCode, Json<serde_json::Value>) {
    (
        status,
        Json(serde_json::json!({
            "error": { "code": code, "message": message }
        })),
    )
}

fn validate_email(email: &str) -> bool {
    let trimmed = email.trim();
    !trimmed.is_empty() && trimmed.contains('@') && trimmed.len() <= 255
}

fn validate_password(password: &str) -> bool {
    password.len() >= 8 && password.len() <= 128
}

// -- Extension types inserted by auth middleware --

/// Inserted by auth middleware when a session token is validated.
#[derive(Debug, Clone, serde::Serialize)]
pub struct SessionUser(pub User);

impl std::ops::Deref for SessionUser {
    type Target = User;
    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

/// Inserted by auth middleware — the raw session token for logout.
#[derive(Debug, Clone)]
pub struct SessionToken(pub String);

// -- Handlers --

/// GET /v1/auth/setup-status
pub async fn setup_status(State(state): State<AppState>) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match has_users(pool).await {
        Ok(has) => (
            StatusCode::OK,
            Json(serde_json::json!({ "needs_setup": !has })),
        )
            .into_response(),
        Err(e) => {
            warn!("setup_status: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to check setup status",
            )
            .into_response()
        }
    }
}

/// POST /v1/auth/setup
pub async fn setup(
    State(state): State<AppState>,
    Json(body): Json<SetupRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match has_users(pool).await {
        Ok(true) => {
            return error_response(StatusCode::FORBIDDEN, "FORBIDDEN", "Setup already completed")
                .into_response()
        }
        Err(e) => {
            warn!("setup: db error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Database error",
            )
            .into_response();
        }
        Ok(false) => {}
    }

    if !validate_email(&body.email) {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Invalid email")
            .into_response();
    }
    if !validate_password(&body.password) {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Password must be 8-128 characters",
        )
        .into_response();
    }
    if body.display_name.trim().is_empty() || body.display_name.len() > 128 {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Display name must be 1-128 characters",
        )
        .into_response();
    }

    let pw_hash = match hash_password(&body.password) {
        Ok(h) => h,
        Err(e) => {
            warn!("setup: password hash error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to hash password",
            )
            .into_response();
        }
    };

    let user = match create_user(pool, &body.email, &pw_hash, &body.display_name, "admin").await {
        Ok(u) => u,
        Err(e) => {
            warn!("setup: create user error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create user",
            )
            .into_response();
        }
    };

    let token = match create_session(pool, user.id).await {
        Ok(t) => t,
        Err(e) => {
            warn!("setup: create session error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create session",
            )
            .into_response();
        }
    };

    info!(user_id = %user.id, email = %user.email, "initial admin account created");
    (
        StatusCode::CREATED,
        Json(serde_json::json!({ "token": token, "user": user })),
    )
        .into_response()
}

/// POST /v1/auth/login
pub async fn login(
    State(state): State<AppState>,
    Json(body): Json<LoginRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    let user_row = match find_user_by_email(pool, &body.email).await {
        Ok(Some(u)) => u,
        Ok(None) => {
            return error_response(
                StatusCode::UNAUTHORIZED,
                "UNAUTHORIZED",
                "Invalid email or password",
            )
            .into_response()
        }
        Err(e) => {
            warn!("login: db error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Database error",
            )
            .into_response();
        }
    };

    if !verify_password(&body.password, &user_row.password_hash) {
        return error_response(
            StatusCode::UNAUTHORIZED,
            "UNAUTHORIZED",
            "Invalid email or password",
        )
        .into_response();
    }

    let token = match create_session(pool, user_row.id).await {
        Ok(t) => t,
        Err(e) => {
            warn!("login: create session error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create session",
            )
            .into_response();
        }
    };

    let user = User {
        id: user_row.id,
        email: user_row.email,
        display_name: user_row.display_name,
        role: user_row.role,
        created_at: user_row.created_at,
        updated_at: user_row.updated_at,
    };

    info!(user_id = %user.id, "user logged in");
    (
        StatusCode::OK,
        Json(serde_json::json!({ "token": token, "user": user })),
    )
        .into_response()
}

/// POST /v1/auth/signup
pub async fn signup(
    State(state): State<AppState>,
    Json(body): Json<SignupRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    if !validate_email(&body.email) {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Invalid email")
            .into_response();
    }
    if !validate_password(&body.password) {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Password must be 8-128 characters",
        )
        .into_response();
    }
    if body.display_name.trim().is_empty() || body.display_name.len() > 128 {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Display name must be 1-128 characters",
        )
        .into_response();
    }

    // Validate invite code
    let invite: Option<InviteRow> = sqlx::query_as(
        "SELECT id, code, role, used_by, expires_at FROM invites WHERE code = $1",
    )
    .bind(&body.invite_code)
    .fetch_optional(pool)
    .await
    .unwrap_or(None);

    let invite = match invite {
        Some(inv) => inv,
        None => {
            return error_response(
                StatusCode::BAD_REQUEST,
                "INVALID_INVITE",
                "Invalid invite code",
            )
            .into_response()
        }
    };

    if invite.used_by.is_some() {
        return error_response(
            StatusCode::BAD_REQUEST,
            "INVITE_USED",
            "Invite code already used",
        )
        .into_response();
    }
    if invite.expires_at < chrono::Utc::now() {
        return error_response(
            StatusCode::BAD_REQUEST,
            "INVITE_EXPIRED",
            "Invite code has expired",
        )
        .into_response();
    }

    let pw_hash = match hash_password(&body.password) {
        Ok(h) => h,
        Err(e) => {
            warn!("signup: password hash error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to hash password",
            )
            .into_response();
        }
    };

    let user =
        match create_user(pool, &body.email, &pw_hash, &body.display_name, &invite.role).await {
            Ok(u) => u,
            Err(e) if e.to_string().contains("duplicate key") => {
                return error_response(
                    StatusCode::CONFLICT,
                    "EMAIL_TAKEN",
                    "Email already registered",
                )
                .into_response();
            }
            Err(e) => {
                warn!("signup: create user error: {e}");
                return error_response(
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "INTERNAL_ERROR",
                    "Failed to create user",
                )
                .into_response();
            }
        };

    // Mark invite as used
    let _ = sqlx::query("UPDATE invites SET used_by = $1 WHERE id = $2")
        .bind(user.id)
        .bind(invite.id)
        .execute(pool)
        .await;

    let token = match create_session(pool, user.id).await {
        Ok(t) => t,
        Err(e) => {
            warn!("signup: create session error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create session",
            )
            .into_response();
        }
    };

    info!(user_id = %user.id, email = %user.email, "user signed up via invite");
    (
        StatusCode::CREATED,
        Json(serde_json::json!({ "token": token, "user": user })),
    )
        .into_response()
}

/// GET /v1/auth/me
pub async fn me(Extension(user): Extension<SessionUser>) -> impl IntoResponse {
    (StatusCode::OK, Json(serde_json::json!({ "user": user.0 }))).into_response()
}

/// POST /v1/auth/logout
pub async fn logout(
    State(state): State<AppState>,
    Extension(token): Extension<SessionToken>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };
    let _ = revoke_session(pool, &token.0).await;
    (StatusCode::OK, Json(serde_json::json!({ "status": "ok" }))).into_response()
}

/// PUT /v1/auth/password
pub async fn change_password(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Json(body): Json<ChangePasswordRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    if !validate_password(&body.new_password) {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "New password must be 8-128 characters",
        )
        .into_response();
    }

    let user_row = match find_user_by_email(pool, &user.email).await {
        Ok(Some(u)) => u,
        _ => {
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to verify current password",
            )
            .into_response()
        }
    };

    if !verify_password(&body.current_password, &user_row.password_hash) {
        return error_response(
            StatusCode::UNAUTHORIZED,
            "UNAUTHORIZED",
            "Current password is incorrect",
        )
        .into_response();
    }

    let new_hash = match hash_password(&body.new_password) {
        Ok(h) => h,
        Err(e) => {
            warn!("change_password: hash error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to hash password",
            )
            .into_response();
        }
    };

    match sqlx::query("UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2")
        .bind(&new_hash)
        .bind(user.id)
        .execute(pool)
        .await
    {
        Ok(_) => {
            info!(user_id = %user.id, "password changed");
            (StatusCode::OK, Json(serde_json::json!({ "status": "ok" }))).into_response()
        }
        Err(e) => {
            warn!("change_password: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to update password",
            )
            .into_response()
        }
    }
}

// -- Supporting types --

#[derive(Debug, sqlx::FromRow)]
struct InviteRow {
    id: uuid::Uuid,
    #[allow(dead_code)]
    code: String,
    role: String,
    used_by: Option<uuid::Uuid>,
    expires_at: chrono::DateTime<chrono::Utc>,
}
