use anyhow::Result;
use clap::Parser;
use std::sync::Arc;
use tracing::info;

use bigrag_common::config::{ServerConfig, StorageConfig, CacheConfig, WalConfig, CompactionConfig};
use bigrag_api::routes::create_router;
use bigrag_api::state::AppState;
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
    #[arg(short, long, default_value = "3000")]
    port: u16,

    /// Storage path (local mode)
    #[arg(long, default_value = "./data")]
    data_dir: String,

    /// API keys (comma-separated)
    #[arg(long, env = "BIGRAG_API_KEYS")]
    api_keys: Option<String>,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "bigrag=info,tower_http=info".into()),
        )
        .init();

    let cli = Cli::parse();

    // Build config
    let config = ServerConfig {
        host: cli.host.clone(),
        port: cli.port,
        metrics_port: 9090,
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

    info!(
        host = %config.host,
        port = config.port,
        data_dir = %cli.data_dir,
        "starting bigRAG"
    );

    // Initialize storage engine
    let (engine, background) = StorageEngine::open(&config).await?;
    let engine = Arc::new(engine);

    // Spawn background tasks (WAL processor, compaction)
    let _bg_handles = background.spawn();

    // Parse API keys
    let api_keys: Vec<String> = cli
        .api_keys
        .map(|k| k.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect())
        .unwrap_or_default();

    // Build app state and router
    let state = AppState::new(engine, api_keys);
    let app = create_router(state);

    // Add tower-http layers
    let app = app.layer(
        tower_http::trace::TraceLayer::new_for_http()
    ).layer(
        tower_http::compression::CompressionLayer::new()
    ).layer(
        tower_http::cors::CorsLayer::permissive()
    );

    // Start server
    let addr = format!("{}:{}", config.host, config.port);
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("listening on {addr}");

    axum::serve(listener, app).await?;

    Ok(())
}
