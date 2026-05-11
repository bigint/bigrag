use std::time::Duration;

use thiserror::Error;

/// Errors returned by the bigRAG SDK.
#[derive(Error, Debug)]
pub enum BigRagError {
    /// 400 Bad Request — validation error or malformed input.
    #[error("bad request: {message}")]
    BadRequest {
        /// Error detail from the API.
        message: String,
        /// HTTP status code.
        status: u16,
    },

    /// 401/403 — missing or invalid API key.
    #[error("authentication failed: {message}")]
    Authentication {
        /// Error detail from the API.
        message: String,
    },

    /// 404 — resource does not exist.
    #[error("not found: {message}")]
    NotFound {
        /// Error detail from the API.
        message: String,
    },

    /// 409 — resource conflict (e.g. duplicate collection name).
    #[error("conflict: {message}")]
    Conflict {
        /// Error detail from the API.
        message: String,
    },

    /// 429 from proxy or infrastructure layers.
    #[error("rate limited")]
    RateLimited,

    /// 5xx — server-side failure.
    #[error("server error: {message}")]
    ServerError {
        /// Error detail from the API.
        message: String,
        /// HTTP status code.
        status: u16,
    },

    /// Request timed out.
    #[error("request timed out after {0:?}")]
    Timeout(Duration),

    /// Network or connection failure.
    #[error("connection failed: {0}")]
    Connection(String),

    /// Failed to read a local file for upload.
    #[error("failed to read file: {0}")]
    FileRead(#[from] std::io::Error),

    /// JSON serialization or deserialization error.
    #[error("serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Unmapped HTTP status code.
    #[error("unexpected status {status}: {message}")]
    Api {
        /// HTTP status code.
        status: u16,
        /// Error detail from the API.
        message: String,
    },
}

impl BigRagError {
    /// Returns the HTTP status code if this was an API error.
    pub fn status(&self) -> Option<u16> {
        match self {
            Self::BadRequest { status, .. } => Some(*status),
            Self::Authentication { .. } => Some(401),
            Self::NotFound { .. } => Some(404),
            Self::Conflict { .. } => Some(409),
            Self::RateLimited => Some(429),
            Self::ServerError { status, .. } => Some(*status),
            Self::Api { status, .. } => Some(*status),
            Self::Timeout(_) | Self::Connection(_) | Self::FileRead(_) | Self::Serialization(_) => {
                None
            }
        }
    }

    /// Whether the error is transient and the request could be retried.
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            Self::RateLimited | Self::ServerError { .. } | Self::Timeout(_) | Self::Connection(_)
        )
    }
}

/// Parse an HTTP response into a `BigRagError`.
///
/// Extracts the error message from FastAPI's `{"detail": "..."}` format,
/// with fallbacks to `{"error": {"message": "..."}}` and `{"message": "..."}`.
pub(crate) async fn parse_error_response(response: reqwest::Response) -> BigRagError {
    let status = response.status().as_u16();
    let body: serde_json::Value = response.json().await.unwrap_or_default();

    let message = body
        .get("detail")
        .and_then(|v| v.as_str())
        .or_else(|| {
            body.get("error")
                .and_then(|e| e.get("message"))
                .and_then(|v| v.as_str())
        })
        .or_else(|| body.get("message").and_then(|v| v.as_str()))
        .unwrap_or("unknown error")
        .to_string();

    match status {
        400 => BigRagError::BadRequest { message, status },
        401 | 403 => BigRagError::Authentication { message },
        404 => BigRagError::NotFound { message },
        409 => BigRagError::Conflict { message },
        429 => BigRagError::RateLimited,
        500..=599 => BigRagError::ServerError { message, status },
        _ => BigRagError::Api { status, message },
    }
}
