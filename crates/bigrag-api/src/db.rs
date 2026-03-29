use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::time::Duration;
use tracing::info;

/// Initialize a Postgres connection pool and run pending migrations.
pub async fn init_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    let pool = PgPoolOptions::new()
        .max_connections(10)
        .acquire_timeout(Duration::from_secs(5))
        .connect(database_url)
        .await?;

    info!("connected to Postgres, running migrations");
    sqlx::migrate!("./migrations").run(&pool).await?;
    info!("migrations complete");

    Ok(pool)
}
