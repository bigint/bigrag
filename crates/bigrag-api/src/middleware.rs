use axum::{
    extract::Request,
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};

use crate::state::AppState;

/// Extract bearer token from Authorization header.
pub fn extract_bearer_token(headers: &HeaderMap) -> Option<String> {
    headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .map(|s| s.to_string())
}

/// Authentication middleware.
pub async fn auth_middleware(
    axum::extract::State(state): axum::extract::State<AppState>,
    request: Request,
    next: Next,
) -> Response {
    // Skip auth if no API keys configured
    if state.api_keys.is_empty() {
        return next.run(request).await;
    }

    let token = extract_bearer_token(request.headers());

    match token {
        Some(ref t) if state.validate_auth(t) => next.run(request).await,
        Some(_) => (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "status": "error",
                "error": "invalid API key"
            })),
        )
            .into_response(),
        None => (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "status": "error",
                "error": "authentication required"
            })),
        )
            .into_response(),
    }
}
