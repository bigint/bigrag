use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{Duration, Utc};
use rand::RngCore;
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use uuid::Uuid;

/// Generate a cryptographically random session token (base64url, 32 bytes).
pub fn generate_token() -> String {
    let mut bytes = [0u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    URL_SAFE_NO_PAD.encode(bytes)
}

/// SHA-256 hash a token for storage. Returns hex string.
pub fn hash_token(token: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(token.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// User row from the database.
#[derive(Debug, Clone, serde::Serialize, sqlx::FromRow)]
pub struct User {
    pub id: Uuid,
    pub email: String,
    pub display_name: String,
    pub role: String,
    pub created_at: chrono::DateTime<Utc>,
    pub updated_at: chrono::DateTime<Utc>,
}

/// Internal user row including password hash (never serialized to clients).
#[derive(Debug, sqlx::FromRow)]
pub struct UserRow {
    pub id: Uuid,
    pub email: String,
    pub password_hash: String,
    pub display_name: String,
    pub role: String,
    pub created_at: chrono::DateTime<Utc>,
    pub updated_at: chrono::DateTime<Utc>,
}

/// Create a new session for a user. Returns the plaintext token.
pub async fn create_session(pool: &PgPool, user_id: Uuid) -> Result<String, sqlx::Error> {
    let token = generate_token();
    let token_hash = hash_token(&token);
    let expires_at = Utc::now() + Duration::days(7);

    sqlx::query("INSERT INTO sessions (user_id, token_hash, expires_at) VALUES ($1, $2, $3)")
        .bind(user_id)
        .bind(&token_hash)
        .bind(expires_at)
        .execute(pool)
        .await?;

    Ok(token)
}

/// Validate a session token. Returns the user if valid and not expired.
pub async fn validate_session(pool: &PgPool, token: &str) -> Result<Option<User>, sqlx::Error> {
    let token_hash = hash_token(token);

    let row = sqlx::query_as::<_, User>(
        r#"
        SELECT u.id, u.email, u.display_name, u.role, u.created_at, u.updated_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token_hash = $1 AND s.expires_at > now()
        "#,
    )
    .bind(&token_hash)
    .fetch_optional(pool)
    .await?;

    Ok(row)
}

/// Revoke a session by token.
pub async fn revoke_session(pool: &PgPool, token: &str) -> Result<(), sqlx::Error> {
    let token_hash = hash_token(token);
    sqlx::query("DELETE FROM sessions WHERE token_hash = $1")
        .bind(&token_hash)
        .execute(pool)
        .await?;
    Ok(())
}

/// Check if any users exist in the database.
pub async fn has_users(pool: &PgPool) -> Result<bool, sqlx::Error> {
    let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM users")
        .fetch_one(pool)
        .await?;
    Ok(row.0 > 0)
}

/// Find a user by email (with password hash for login verification).
pub async fn find_user_by_email(
    pool: &PgPool,
    email: &str,
) -> Result<Option<UserRow>, sqlx::Error> {
    let row = sqlx::query_as::<_, UserRow>(
        "SELECT id, email, password_hash, display_name, role, created_at, updated_at FROM users WHERE email = $1",
    )
    .bind(email)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Create a new user. Returns the user (without password hash).
pub async fn create_user(
    pool: &PgPool,
    email: &str,
    password_hash: &str,
    display_name: &str,
    role: &str,
) -> Result<User, sqlx::Error> {
    let user = sqlx::query_as::<_, User>(
        r#"
        INSERT INTO users (email, password_hash, display_name, role)
        VALUES ($1, $2, $3, $4)
        RETURNING id, email, display_name, role, created_at, updated_at
        "#,
    )
    .bind(email)
    .bind(password_hash)
    .bind(display_name)
    .bind(role)
    .fetch_one(pool)
    .await?;
    Ok(user)
}
