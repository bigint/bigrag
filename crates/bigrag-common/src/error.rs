use serde::Serialize;

#[derive(Debug, thiserror::Error)]
pub enum BigRagError {
    #[error("bad request: {0}")]
    BadRequest(String),

    #[error("authentication required")]
    AuthenticationError,

    #[error("permission denied: {0}")]
    PermissionDenied(String),

    #[error("not found: {0}")]
    NotFound(String),

    #[error("unprocessable entity: {0}")]
    UnprocessableEntity(String),

    #[error("rate limited: {0}")]
    RateLimited(String),

    #[error("index not ready")]
    IndexNotReady,

    #[error("internal error: {0}")]
    Internal(String),

    #[error("storage error: {0}")]
    Storage(String),

    #[error("cas conflict: {0}")]
    CasConflict(String),

    #[error("epoch fenced: writer {current} fenced by {winner}")]
    EpochFenced { current: u64, winner: u64 },
}

impl BigRagError {
    pub fn status_code(&self) -> u16 {
        match self {
            Self::BadRequest(_) => 400,
            Self::AuthenticationError => 401,
            Self::PermissionDenied(_) => 403,
            Self::NotFound(_) => 404,
            Self::UnprocessableEntity(_) => 422,
            Self::RateLimited(_) => 429,
            Self::IndexNotReady => 202,
            Self::Internal(_) | Self::Storage(_) | Self::CasConflict(_) | Self::EpochFenced { .. } => 500,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub status: &'static str,
    pub error: String,
}

impl From<&BigRagError> for ErrorResponse {
    fn from(e: &BigRagError) -> Self {
        Self {
            status: "error",
            error: e.to_string(),
        }
    }
}

pub type Result<T> = std::result::Result<T, BigRagError>;
