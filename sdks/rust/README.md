# rag-computer

Rust client for [rag.computer](https://github.com/yoginth/rag-computer) — a self-hostable RAG platform.

## Installation

```toml
[dependencies]
rag-computer = "2026.5.7"
tokio = { version = "1", features = ["full"] }
```

## Quick Start

```rust,no_run
use rag_computer::RagComputer;

#[tokio::main]
async fn main() -> Result<(), rag_computer::RagComputerError> {
    let client = RagComputer::new("http://localhost:4000", "your-api-key");

    // Create a collection
    let collection = client.collections().create(rag_computer::types::collections::CreateCollectionBody {
        name: "my-docs".into(),
        ..Default::default()
    }).await?;

    // Upload a document
    let doc = client.documents().upload("my-docs", "/path/to/file.pdf", None).await?;

    // Query
    let results = client.queries().query("my-docs", rag_computer::types::query::QueryBody {
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
| `RAG_COMPUTER_BASE_URL` | `http://localhost:4000` | Base URL of the rag.computer API |
| `RAG_COMPUTER_API_KEY` | — | API key for authentication |

Use `RagComputer::from_env()` to read these automatically.

## Resources

- `client.collections()` for collection CRUD, stats, re-embedding, and event streams.
- `client.documents()` for uploads, batch operations, file URLs, and status polling.
- `client.queries()` for single, multi-collection, and batch retrieval queries.
- `client.chat()` for generated answers and conversation CRUD.
- `client.vectors()` for raw vector upsert and delete.
- `client.webhooks()` for webhook management and delivery replay.
- `client.auth()` for setup, login, identity, password, and preferences.
- `client.admin()` for users, API keys, access logs, audit logs, connector config, embedding presets, and MCP server keys.
- `client.connectors().google()` for Google Drive account, file browsing, sources, and sync jobs.
- `client.evaluations()` for golden-set retrieval evaluations.

## Builder API

```rust,no_run
use std::time::Duration;
use rag_computer::RagComputer;

# fn main() -> Result<(), rag_computer::RagComputerError> {
let client = RagComputer::builder()
    .base_url("https://my-rag.computer")
    .api_key("sk-...")
    .timeout(Duration::from_secs(60))
    .max_retries(3)
    .build()?;
# Ok(())
# }
```

## Collection-Scoped Client

```rust,no_run
use rag_computer::RagComputer;

# async fn example() -> Result<(), rag_computer::RagComputerError> {
let client = RagComputer::new("http://localhost:4000", "sk-...");
let col = client.collection("my-docs");

// All methods scoped to "my-docs"
let docs = col.list_documents(None).await?;
let stats = col.stats().await?;
# Ok(())
# }
```
