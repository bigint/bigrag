# bigrag

Rust client for [bigRAG](https://github.com/bigrag/bigrag) — a self-hostable RAG platform.

## Installation

```toml
[dependencies]
bigrag = "0.1"
tokio = { version = "1", features = ["full"] }
```

## Quick Start

```rust,no_run
use bigrag::BigRag;

#[tokio::main]
async fn main() -> Result<(), bigrag::BigRagError> {
    let client = BigRag::new("http://localhost:6100", "your-api-key");

    // Create a collection
    let collection = client.collections().create(bigrag::types::collections::CreateCollectionBody {
        name: "my-docs".into(),
        ..Default::default()
    }).await?;

    // Upload a document
    let doc = client.documents().upload("my-docs", "/path/to/file.pdf", None).await?;

    // Query
    let results = client.queries().query("my-docs", bigrag::types::query::QueryBody {
        query: "How does it work?".into(),
        ..Default::default()
    }).await?;

    for result in results.results {
        println!("[{:.2}] {}", result.score, result.text);
    }

    Ok(())
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BIGRAG_BASE_URL` | `http://localhost:6100` | Base URL of the bigRAG API |
| `BIGRAG_API_KEY` | — | API key for authentication |

Use `BigRag::from_env()` to read these automatically.

## Builder API

```rust,no_run
use std::time::Duration;
use bigrag::BigRag;

# fn main() -> Result<(), bigrag::BigRagError> {
let client = BigRag::builder()
    .base_url("https://my-bigrag.example.com")
    .api_key("sk-...")
    .timeout(Duration::from_secs(60))
    .max_retries(3)
    .build()?;
# Ok(())
# }
```

## Collection-Scoped Client

```rust,no_run
use bigrag::BigRag;

# async fn example() -> Result<(), bigrag::BigRagError> {
let client = BigRag::new("http://localhost:6100", "sk-...");
let col = client.collection("my-docs");

// All methods scoped to "my-docs"
let docs = col.list_documents(None).await?;
let stats = col.stats().await?;
# Ok(())
# }
```
