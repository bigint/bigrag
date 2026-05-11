//! Basic rag.computer usage: create a collection, upload a document, and query.
//!
//! Run with: `cargo run --example basic_usage`
//! Requires a running rag.computer server at localhost:6100.

use rag_computer::types::{CreateCollectionBody, QueryBody};
use rag_computer::RagComputer;

#[tokio::main]
async fn main() -> Result<(), rag_computer::RagComputerError> {
    let client = RagComputer::from_env()?;

    // Check health
    let health = client.health().await?;
    println!("Server: {} ({})", health.status, health.version);

    // Create a collection
    let collection = client
        .collections()
        .create(CreateCollectionBody {
            name: "example_docs".into(),
            description: Some("Example collection".into()),
            ..Default::default()
        })
        .await?;
    println!("Created collection: {}", collection.name);

    // Upload a document
    let doc = client
        .documents()
        .upload("example_docs", "README.md", None)
        .await?;
    println!("Uploaded: {} ({})", doc.filename, doc.id);

    // Wait for processing
    println!("Waiting for processing...");
    tokio::time::sleep(std::time::Duration::from_secs(5)).await;

    // Query the collection
    let results = client
        .queries()
        .query(
            "example_docs",
            QueryBody {
                query: "What is rag.computer?".into(),
                top_k: Some(3),
                ..Default::default()
            },
        )
        .await?;

    println!("\nResults ({} total):", results.total);
    for r in &results.results {
        println!("  [{:.3}] {}", r.score, &r.text[..r.text.len().min(100)]);
    }

    // Cleanup
    client.collections().delete("example_docs").await?;
    println!("\nCleaned up.");

    Ok(())
}
