//! File upload patterns: path, bytes, batch upload.
//!
//! Run with: `cargo run --example file_upload`
//! Requires a running rag.computer server at localhost:6100.

use rag_computer::types::CreateCollectionBody;
use rag_computer::{FileInput, RagComputer};

#[tokio::main]
async fn main() -> Result<(), rag_computer::RagComputerError> {
    let client = RagComputer::from_env()?;

    // Create a collection for testing
    client
        .collections()
        .create(CreateCollectionBody {
            name: "upload_test".into(),
            ..Default::default()
        })
        .await?;

    // Upload from a file path (simplest)
    let doc = client
        .documents()
        .upload("upload_test", "README.md", None)
        .await?;
    println!("From path: {} ({})", doc.filename, doc.status);

    // Upload from bytes in memory
    let content = b"# Hello\n\nThis is a test document.".to_vec();
    let doc = client
        .documents()
        .upload("upload_test", (content, "hello.md"), None)
        .await?;
    println!("From bytes: {} ({})", doc.filename, doc.status);

    // Upload with metadata
    let meta = serde_json::json!({"department": "engineering", "priority": "high"});
    let doc = client
        .documents()
        .upload("upload_test", "Cargo.toml", Some(meta))
        .await?;
    println!("With metadata: {} ({})", doc.filename, doc.status);

    // Batch upload
    let files = vec![
        FileInput::from("README.md"),
        FileInput::Bytes {
            data: b"Another doc".to_vec(),
            name: "another.txt".into(),
        },
    ];
    let batch = client
        .documents()
        .batch_upload("upload_test", files, None)
        .await?;
    println!("Batch uploaded: {} documents", batch.total);

    // Using the scoped collection client
    let col = client.collection("upload_test");
    let docs = col.list_documents(None).await?;
    println!("\nTotal documents in collection: {}", docs.total);

    // Cleanup
    client.collections().delete("upload_test").await?;
    println!("Cleaned up.");

    Ok(())
}
