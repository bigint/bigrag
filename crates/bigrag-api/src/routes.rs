use axum::{
    Router,
    middleware,
    routing::{delete, get, post},
};

use crate::handlers;
use crate::middleware::auth_middleware;
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
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ));

    Router::new()
        .route("/health", get(handlers::health_check))
        .merge(api_routes)
        .with_state(state)
}
