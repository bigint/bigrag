use axum::{
    extract::Request,
    http::{HeaderMap, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use tracing::{debug, trace, warn};
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
/// Validates the bearer token (API key or JWT) and inserts the resolved
/// `ApiKey` into request extensions so handlers can perform permission checks.
pub async fn auth_middleware(
    axum::extract::State(state): axum::extract::State<AppState>,
    mut request: Request,
    next: Next,
) -> Response {
    // If no keys are configured (open mode), allow all requests
    if state.key_store.is_open() && state.jwt_config.is_none() {
        trace!("auth: open mode, allowing request");
        return next.run(request).await;
    }

    let token = extract_bearer_token(request.headers());

    match token {
        Some(ref t) => match state.validate_auth(t) {
            Some(api_key) => {
                debug!(key_id = %api_key.id, key_name = %api_key.name, "auth: request authenticated");
                request.extensions_mut().insert(api_key);
                next.run(request).await
            }
            None => {
                warn!("auth: invalid API key or JWT token");
                (
                    StatusCode::UNAUTHORIZED,
                    Json(serde_json::json!({
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Invalid API key"
                        }
                    })),
                )
                    .into_response()
            }
        },
        None => {
            warn!("auth: missing Authorization header");
            (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing Authorization header"
                    }
                })),
            )
                .into_response()
        }
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

    debug!(
        method = %method,
        path = %path,
        status,
        duration_ms = duration.as_secs_f64() * 1000.0,
        request_id = %request_id,
        "request completed"
    );

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
