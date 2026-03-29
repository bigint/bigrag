use axum::{
    middleware,
    routing::{delete, get, post, put},
    Router,
};

use crate::auth;
use crate::handlers;
use crate::middleware::{auth_middleware, request_tracking};
use crate::state::AppState;

pub fn create_router(state: AppState) -> Router {
    let api_routes = Router::new()
        // v2 endpoints
        .route(
            "/v2/namespaces/{namespace}",
            post(handlers::write_documents),
        )
        .route(
            "/v2/namespaces/{namespace}/query",
            post(handlers::query_documents),
        )
        .route(
            "/v2/namespaces/{namespace}/explain_query",
            post(handlers::explain_query),
        )
        .route(
            "/v2/namespaces/{namespace}",
            delete(handlers::delete_namespace),
        )
        // v1 endpoints
        .route(
            "/v1/namespaces/{namespace}/metadata",
            get(handlers::get_namespace_metadata),
        )
        .route(
            "/v1/namespaces/{namespace}/hint_cache_warm",
            get(handlers::hint_cache_warm),
        )
        .route("/v1/namespaces", get(handlers::list_namespaces))
        .route(
            "/v1/namespaces/{namespace}/_debug/recall",
            post(handlers::debug_recall),
        )
        // Schema
        .route(
            "/v1/namespaces/{namespace}/schema",
            get(handlers::get_schema).put(handlers::update_schema),
        )
        // Single document
        .route(
            "/v1/namespaces/{namespace}/documents/{id}",
            get(handlers::get_document),
        )
        // Admin
        .route(
            "/v1/admin/compact/{namespace}",
            post(handlers::admin_compact),
        )
        .route(
            "/v1/admin/warm/{namespace}",
            post(handlers::admin_warm),
        )
        .route("/v1/admin/config", get(handlers::admin_config))
        // API key management
        .route(
            "/v1/admin/api-keys",
            post(handlers::create_api_key).get(handlers::list_api_keys),
        )
        .route(
            "/v1/admin/api-keys/{id}",
            delete(handlers::revoke_api_key),
        )
        // Export
        .route(
            "/v1/namespaces/{namespace}/export",
            post(handlers::export_namespace),
        )
        // Copy namespace
        .route(
            "/v1/namespaces/{namespace}/copy",
            post(handlers::copy_namespace),
        )
        // Auth (protected)
        .route("/v1/auth/me", get(auth::handlers::me))
        .route("/v1/auth/logout", post(auth::handlers::logout))
        .route(
            "/v1/auth/password",
            put(auth::handlers::change_password),
        )
        // Admin user management
        .route("/v1/admin/users", get(auth::admin::list_users))
        .route(
            "/v1/admin/users/{id}",
            delete(auth::admin::delete_user).patch(auth::admin::update_user),
        )
        // Admin invite management
        .route(
            "/v1/admin/invites",
            post(auth::admin::create_invite).get(auth::admin::list_invites),
        )
        .route(
            "/v1/admin/invites/{id}",
            delete(auth::admin::delete_invite),
        )
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ));

    let auth_public_routes = Router::new()
        .route(
            "/v1/auth/setup-status",
            get(auth::handlers::setup_status),
        )
        .route("/v1/auth/setup", post(auth::handlers::setup))
        .route("/v1/auth/login", post(auth::handlers::login))
        .route("/v1/auth/signup", post(auth::handlers::signup));

    Router::new()
        .route("/health", get(handlers::health_check))
        .route("/v1/health/ready", get(handlers::readiness_probe))
        .route("/v1/health/live", get(handlers::liveness_probe))
        .route("/v1/metrics", get(handlers::prometheus_metrics))
        .merge(auth_public_routes)
        .merge(api_routes)
        .layer(middleware::from_fn(request_tracking))
        .with_state(state)
}
