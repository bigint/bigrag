use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use tracing::info;

/// Initialize a Postgres connection pool and run pending migrations.
pub async fn init_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    let pool = PgPoolOptions::new()
        .max_connections(10)
        .connect(database_url)
        .await?;

    info!("connected to Postgres, running migrations");
    sqlx::migrate!("./migrations").run(&pool).await?;
    info!("migrations complete");

    Ok(pool)
}
