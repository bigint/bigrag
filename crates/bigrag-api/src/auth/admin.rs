use axum::{
    extract::{Extension, Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{Duration, Utc};
use rand::RngCore;
use serde::Deserialize;
use tracing::{info, warn};
use uuid::Uuid;

use super::handlers::{error_response, SessionUser};
use super::session::User;
use crate::state::AppState;

// -- Request types --

#[derive(Debug, Deserialize)]
pub struct CreateInviteRequest {
    #[serde(default = "default_role")]
    pub role: String,
    pub expires_in_hours: Option<i64>,
}

fn default_role() -> String {
    "member".to_string()
}

#[derive(Debug, Deserialize)]
pub struct UpdateUserRequest {
    pub role: String,
}

// -- Helpers --

fn generate_invite_code() -> String {
    let mut bytes = [0u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    URL_SAFE_NO_PAD.encode(bytes)
}

fn require_admin_user(user: &SessionUser) -> Result<(), (StatusCode, Json<serde_json::Value>)> {
    if user.role != "admin" {
        return Err(error_response(StatusCode::FORBIDDEN, "FORBIDDEN", "Admin permissions required"));
    }
    Ok(())
}

// -- Handlers --

/// GET /v1/admin/users
pub async fn list_users(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }
    let Some(ref pool) = state.db_pool else {
        return error_response(StatusCode::SERVICE_UNAVAILABLE, "NO_DATABASE", "Database not configured").into_response();
    };

    match sqlx::query_as::<_, User>(
        "SELECT id, email, display_name, role, created_at, updated_at FROM users ORDER BY created_at"
    )
    .fetch_all(pool)
    .await
    {
        Ok(users) => (StatusCode::OK, Json(serde_json::json!({ "users": users }))).into_response(),
        Err(e) => {
            warn!("list_users: db error: {e}");
            error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to list users").into_response()
        }
    }
}

/// DELETE /v1/admin/users/{id}
pub async fn delete_user(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }
    if user.id == id {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Cannot delete your own account").into_response();
    }
    let Some(ref pool) = state.db_pool else {
        return error_response(StatusCode::SERVICE_UNAVAILABLE, "NO_DATABASE", "Database not configured").into_response();
    };

    match sqlx::query("DELETE FROM users WHERE id = $1").bind(id).execute(pool).await {
        Ok(result) if result.rows_affected() > 0 => {
            info!(user_id = %id, "user deleted by admin {}", user.id);
            (StatusCode::OK, Json(serde_json::json!({ "status": "ok", "message": "User deleted" }))).into_response()
        }
        Ok(_) => error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "User not found").into_response(),
        Err(e) => {
            warn!("delete_user: db error: {e}");
            error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to delete user").into_response()
        }
    }
}

/// PATCH /v1/admin/users/{id}
pub async fn update_user(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Path(id): Path<Uuid>,
    Json(body): Json<UpdateUserRequest>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }
    if body.role != "admin" && body.role != "member" {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Role must be 'admin' or 'member'").into_response();
    }
    let Some(ref pool) = state.db_pool else {
        return error_response(StatusCode::SERVICE_UNAVAILABLE, "NO_DATABASE", "Database not configured").into_response();
    };

    match sqlx::query("UPDATE users SET role = $1, updated_at = now() WHERE id = $2")
        .bind(&body.role)
        .bind(id)
        .execute(pool)
        .await
    {
        Ok(result) if result.rows_affected() > 0 => {
            info!(user_id = %id, new_role = %body.role, "user role updated by admin {}", user.id);
            (StatusCode::OK, Json(serde_json::json!({ "status": "ok" }))).into_response()
        }
        Ok(_) => error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "User not found").into_response(),
        Err(e) => {
            warn!("update_user: db error: {e}");
            error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to update user").into_response()
        }
    }
}

/// POST /v1/admin/invites
pub async fn create_invite(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Json(body): Json<CreateInviteRequest>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }
    if body.role != "admin" && body.role != "member" {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Role must be 'admin' or 'member'").into_response();
    }
    let Some(ref pool) = state.db_pool else {
        return error_response(StatusCode::SERVICE_UNAVAILABLE, "NO_DATABASE", "Database not configured").into_response();
    };

    let code = generate_invite_code();
    let hours = body.expires_in_hours.unwrap_or(168);
    let expires_at = Utc::now() + Duration::hours(hours);

    match sqlx::query_as::<_, InviteResponse>(
        r#"
        INSERT INTO invites (code, role, created_by, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, code, role, expires_at, created_at
        "#,
    )
    .bind(&code)
    .bind(&body.role)
    .bind(user.id)
    .bind(expires_at)
    .fetch_one(pool)
    .await
    {
        Ok(invite) => {
            info!(invite_id = %invite.id, role = %invite.role, "invite created by {}", user.id);
            (StatusCode::CREATED, Json(serde_json::json!(invite))).into_response()
        }
        Err(e) => {
            warn!("create_invite: db error: {e}");
            error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to create invite").into_response()
        }
    }
}

/// GET /v1/admin/invites
pub async fn list_invites(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }
    let Some(ref pool) = state.db_pool else {
        return error_response(StatusCode::SERVICE_UNAVAILABLE, "NO_DATABASE", "Database not configured").into_response();
    };

    match sqlx::query_as::<_, InviteListItem>(
        r#"
        SELECT i.id, i.code, i.role, i.expires_at, i.created_at, i.used_by,
               u.email as created_by_email
        FROM invites i
        JOIN users u ON i.created_by = u.id
        ORDER BY i.created_at DESC
        "#,
    )
    .fetch_all(pool)
    .await
    {
        Ok(invites) => (StatusCode::OK, Json(serde_json::json!({ "invites": invites }))).into_response(),
        Err(e) => {
            warn!("list_invites: db error: {e}");
            error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to list invites").into_response()
        }
    }
}

/// DELETE /v1/admin/invites/{id}
pub async fn delete_invite(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }
    let Some(ref pool) = state.db_pool else {
        return error_response(StatusCode::SERVICE_UNAVAILABLE, "NO_DATABASE", "Database not configured").into_response();
    };

    match sqlx::query("DELETE FROM invites WHERE id = $1 AND used_by IS NULL")
        .bind(id)
        .execute(pool)
        .await
    {
        Ok(result) if result.rows_affected() > 0 => {
            info!(invite_id = %id, "invite revoked by {}", user.id);
            (StatusCode::OK, Json(serde_json::json!({ "status": "ok", "message": "Invite revoked" }))).into_response()
        }
        Ok(_) => error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "Invite not found or already used").into_response(),
        Err(e) => {
            warn!("delete_invite: db error: {e}");
            error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to revoke invite").into_response()
        }
    }
}

// -- Response types --

#[derive(Debug, serde::Serialize, sqlx::FromRow)]
struct InviteResponse {
    id: Uuid,
    code: String,
    role: String,
    expires_at: chrono::DateTime<Utc>,
    created_at: chrono::DateTime<Utc>,
}

#[derive(Debug, serde::Serialize, sqlx::FromRow)]
struct InviteListItem {
    id: Uuid,
    code: String,
    role: String,
    expires_at: chrono::DateTime<Utc>,
    created_at: chrono::DateTime<Utc>,
    used_by: Option<Uuid>,
    created_by_email: String,
}
