use anyhow::Result;
use clap::Parser;
use figment::{
    providers::{Env, Format, Serialized, Toml},
    Figment,
};
use metrics_exporter_prometheus::PrometheusBuilder;
use std::sync::Arc;
use tokio::signal;
use tracing::info;

use bigrag_api::metrics::register_metrics;
use bigrag_api::routes::create_router;
use bigrag_api::state::{ApiKeyStore, AppState, JwtConfig};
use bigrag_common::config::{
    CacheConfig, CompactionConfig, ServerConfig, StorageConfig, WalConfig,
};
use bigrag_storage::engine::StorageEngine;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[derive(Parser)]
#[command(name = "bigrag", about = "Object-storage-native vector + full-text search engine")]
struct Cli {
    /// Config file path
    #[arg(short, long, default_value = "bigrag.toml")]
    config: String,

    /// Listen host
    #[arg(long, default_value = "0.0.0.0")]
    host: String,

    /// Listen port
    #[arg(short, long, default_value = "8080")]
    port: u16,

    /// Metrics port (Prometheus)
    #[arg(long, default_value = "9090", env = "BIGRAG_METRICS_PORT")]
    metrics_port: u16,

    /// Storage path (local mode)
    #[arg(long, default_value = "./data")]
    data_dir: String,

    /// API keys (comma-separated)
    #[arg(long, env = "BIGRAG_API_KEYS")]
    api_keys: Option<String>,

    /// Master API key (bypasses all permission checks)
    #[arg(long, env = "BIGRAG_MASTER_KEY")]
    master_key: Option<String>,

    /// JWT shared secret for HS256 token validation
    #[arg(long, env = "BIGRAG_JWT_SECRET")]
    jwt_secret: Option<String>,

    /// JWT issuer for validation (optional)
    #[arg(long, env = "BIGRAG_JWT_ISSUER")]
    jwt_issuer: Option<String>,

    /// Log format (text or json)
    #[arg(long, default_value = "text", env = "BIGRAG_LOG_FORMAT")]
    log_format: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize tracing with configurable format
    let env_filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "bigrag=info,tower_http=info".into());

    match cli.log_format.as_str() {
        "json" => {
            tracing_subscriber::fmt()
                .json()
                .with_env_filter(env_filter)
                .init();
        }
        _ => {
            tracing_subscriber::fmt()
                .with_env_filter(env_filter)
                .init();
        }
    }

    // Build config with figment: TOML file -> env vars -> CLI overrides
    let cli_defaults = ServerConfig {
        host: cli.host.clone(),
        port: cli.port,
        metrics_port: cli.metrics_port,
        max_connections: 10000,
        request_timeout_ms: 60000,
        max_request_body_mb: 512,
        storage: StorageConfig::Local {
            path: cli.data_dir.clone(),
        },
        cache: CacheConfig::default(),
        wal: WalConfig::default(),
        compaction: CompactionConfig::default(),
    };

    let config: ServerConfig = Figment::new()
        .merge(Toml::file(&cli.config).nested())
        .merge(Env::prefixed("BIGRAG_").split("_"))
        .merge(Serialized::defaults(cli_defaults.clone()))
        .extract()
        .unwrap_or_else(|e| {
            tracing::warn!("failed to load config via figment ({e}), falling back to CLI defaults");
            cli_defaults
        });

    info!(
        host = %config.host,
        port = config.port,
        metrics_port = cli.metrics_port,
        storage = ?config.storage,
        "starting bigRAG v{}",
        env!("CARGO_PKG_VERSION")
    );

    // Initialize storage engine
    let (engine, background) = StorageEngine::open(&config).await?;
    let engine = Arc::new(engine);

    // Spawn background tasks (WAL processor, compaction)
    let _bg_handles = background.spawn();

    // Initialize Prometheus metrics recorder
    let prometheus_handle = PrometheusBuilder::new()
        .install_recorder()
        .expect("failed to install Prometheus metrics recorder");

    // Register metric descriptions
    register_metrics();

    // Set server info gauge
    metrics::gauge!("bigrag_info", "version" => env!("CARGO_PKG_VERSION").to_string()).set(1.0);

    // Parse API keys and build the key store
    let api_keys: Vec<String> = cli
        .api_keys
        .map(|k| k.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect())
        .unwrap_or_default();

    let key_store = ApiKeyStore::new(cli.master_key, api_keys);

    // Build optional JWT config
    let jwt_config = cli.jwt_secret.map(|secret| JwtConfig {
        secret,
        issuer: cli.jwt_issuer,
    });

    // Build app state and router
    let state = AppState::new(engine, key_store, jwt_config, prometheus_handle);

    // Load persisted namespaces from storage engine
    state.load_all_namespaces().await;

    let app = create_router(state);

    // Add tower-http layers
    let app = app.layer(
        tower_http::trace::TraceLayer::new_for_http()
    ).layer(
        tower_http::compression::CompressionLayer::new()
    ).layer(
        tower_http::cors::CorsLayer::permissive()
    );

    // Start server with graceful shutdown
    let addr = format!("{}:{}", config.host, config.port);
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("listening on {addr}");

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    info!("server shut down gracefully");

    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => { info!("received Ctrl+C, shutting down"); },
        _ = terminate => { info!("received SIGTERM, shutting down"); },
    }
}
