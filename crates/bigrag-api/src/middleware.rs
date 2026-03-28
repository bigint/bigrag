use axum::{
    extract::Request,
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use uuid::Uuid;

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

/// Middleware that tracks request metrics and adds response headers.
pub async fn request_tracking(request: Request, next: Next) -> Response {
    let request_id = request
        .headers()
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(String::from)
        .unwrap_or_else(|| format!("req_{}", Uuid::new_v4().simple()));

    let start = std::time::Instant::now();
    let method = request.method().to_string();
    let path = request.uri().path().to_string();

    let mut response = next.run(request).await;

    let duration = start.elapsed();
    let status = response.status().as_u16();

    // Record HTTP request metrics
    metrics::counter!(
        "bigrag_requests_total",
        "method" => method.clone(),
        "path" => path.clone(),
        "status" => status.to_string()
    )
    .increment(1);
    metrics::histogram!(
        "bigrag_request_duration_seconds",
        "method" => method,
        "path" => path
    )
    .record(duration.as_secs_f64());

    if status >= 400 {
        crate::metrics::record_error(status);
    }

    // Add response headers
    let headers = response.headers_mut();
    if let Ok(val) = request_id.parse() {
        headers.insert("x-request-id", val);
    }
    if let Ok(val) = env!("CARGO_PKG_VERSION").parse() {
        headers.insert("x-bigrag-version", val);
    }

    response
}
