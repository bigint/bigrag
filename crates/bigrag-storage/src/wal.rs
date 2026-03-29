use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, oneshot};
use tracing::{debug, error, info, trace, warn};

use crate::backend::StorageBackend;
use crate::manifest::ManifestManager;
use crate::sst::{Compression, Entry, SstBuilder};

/// A single write operation to be batched.
pub struct WriteOp {
    pub namespace: String,
    pub entries: Vec<Entry>,
    pub result_tx: oneshot::Sender<Result<(), WalError>>,
}

/// WAL writer with group commit.
///
/// Batches concurrent writes to the same namespace into a single object storage PUT.
/// Maximum 1 batch per second per namespace.
pub struct WalWriter {
    batch_tx: mpsc::Sender<WriteOp>,
}

impl WalWriter {
    pub fn new(
        backend: StorageBackend,
        manifest: Arc<ManifestManager>,
        writer_epoch: u64,
    ) -> (Self, WalBatchProcessor) {
        let (batch_tx, batch_rx) = mpsc::channel(10_000);

        let processor = WalBatchProcessor {
            backend,
            manifest,
            writer_epoch,
            batch_rx,
        };

        let writer = Self { batch_tx };

        (writer, processor)
    }

    /// Submit a write operation. Blocks until the write is durably persisted.
    pub async fn write(
        &self,
        namespace: String,
        entries: Vec<Entry>,
    ) -> Result<(), WalError> {
        let (result_tx, result_rx) = oneshot::channel();
        let op = WriteOp {
            namespace,
            entries,
            result_tx,
        };

        self.batch_tx
            .send(op)
            .await
            .map_err(|_| {
                error!("WAL write channel closed");
                WalError::ChannelClosed
            })?;

        result_rx.await.map_err(|_| {
            error!("WAL result channel closed");
            WalError::ChannelClosed
        })?
    }
}

/// Background processor that batches and flushes WAL entries.
pub struct WalBatchProcessor {
    backend: StorageBackend,
    manifest: Arc<ManifestManager>,
    writer_epoch: u64,
    batch_rx: mpsc::Receiver<WriteOp>,
}

impl WalBatchProcessor {
    /// Run the batch processor. This should be spawned as a background task.
    pub async fn run(mut self) {
        let batch_interval = Duration::from_secs(1);

        loop {
            // Collect operations for up to 1 second
            let mut ops: Vec<WriteOp> = Vec::new();
            let deadline = Instant::now() + batch_interval;

            // Wait for the first operation
            match self.batch_rx.recv().await {
                Some(op) => ops.push(op),
                None => {
                    info!("WAL batch processor shutting down");
                    return;
                }
            }

            // Collect more operations until deadline
            loop {
                let remaining = deadline.saturating_duration_since(Instant::now());
                if remaining.is_zero() {
                    break;
                }

                match tokio::time::timeout(remaining, self.batch_rx.recv()).await {
                    Ok(Some(op)) => ops.push(op),
                    Ok(None) => {
                        // Channel closed — flush remaining and exit
                        self.flush_batch(ops).await;
                        return;
                    }
                    Err(_) => break, // Timeout — flush batch
                }
            }

            self.flush_batch(ops).await;
        }
    }

    async fn flush_batch(&self, ops: Vec<WriteOp>) {
        if ops.is_empty() {
            return;
        }

        // Group by namespace
        let mut by_namespace: HashMap<String, Vec<WriteOp>> = HashMap::new();
        for op in ops {
            by_namespace
                .entry(op.namespace.clone())
                .or_default()
                .push(op);
        }

        debug!(
            namespaces = by_namespace.len(),
            "flushing WAL batch"
        );

        // Flush each namespace batch
        for (namespace, ns_ops) in by_namespace {
            let op_count = ns_ops.len();
            let result = self.flush_namespace_batch(&namespace, &ns_ops).await;

            if let Err(ref e) = result {
                error!(namespace = %namespace, ops = op_count, error = %e, "WAL namespace flush failed");
            } else {
                trace!(namespace = %namespace, ops = op_count, "WAL namespace flush succeeded");
            }

            // Notify all waiters
            for op in ns_ops {
                let _ = op.result_tx.send(result.clone());
            }
        }
    }

    async fn flush_namespace_batch(
        &self,
        namespace: &str,
        ops: &[WriteOp],
    ) -> Result<(), WalError> {
        // Combine all entries from all ops
        let mut all_entries = Vec::new();
        for op in ops {
            all_entries.extend(op.entries.iter().cloned());
        }

        if all_entries.is_empty() {
            return Ok(());
        }

        // Build an SST from the entries
        let mut builder = SstBuilder::new(Compression::Lz4);
        builder.add_all(all_entries);
        let sst = builder.build();

        // Allocate a WAL sequence number
        let seq = self.manifest.next_wal_seq();
        let path = StorageBackend::wal_path(namespace, seq);

        // Write to object storage
        self.backend
            .put(&path, sst.data.clone())
            .await
            .map_err(|e| WalError::StorageError(format!("failed to write WAL SST: {e}")))?;

        debug!(
            namespace,
            seq,
            entries = sst.num_entries,
            bytes = sst.data.len(),
            "WAL batch flushed"
        );

        // Update manifest with new WAL SST
        let sst_meta = crate::manifest::SstMeta {
            seq,
            path: path.clone(),
            level: 0,
            size_bytes: sst.data.len() as u64,
            num_entries: sst.num_entries as u64,
            first_key: sst.first_key.as_ref().map(|k| k.to_vec()),
            last_key: sst.last_key.as_ref().map(|k| k.to_vec()),
            writer_epoch: self.writer_epoch,
        };

        self.manifest
            .commit(|state| {
                let ns = state.namespaces.entry(namespace.to_string()).or_insert_with(|| {
                    crate::manifest::NamespaceState {
                        wal_ssts: vec![],
                        sorted_runs: vec![],
                        schema: None,
                        distance_metric: None,
                        created_at: chrono::Utc::now().to_rfc3339(),
                        updated_at: chrono::Utc::now().to_rfc3339(),
                    }
                });
                ns.wal_ssts.push(sst_meta);
                ns.updated_at = chrono::Utc::now().to_rfc3339();
            })
            .await
            .map_err(|e| WalError::ManifestError(format!("{e}")))?;

        Ok(())
    }
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum WalError {
    #[error("channel closed")]
    ChannelClosed,

    #[error("storage error: {0}")]
    StorageError(String),

    #[error("manifest error: {0}")]
    ManifestError(String),

    #[error("epoch fenced")]
    EpochFenced,
}

#[cfg(test)]
mod tests {
    use super::*;
    use bigrag_common::config::StorageConfig;
    use bytes::Bytes;

    #[tokio::test]
    async fn test_wal_write_and_flush() {
        let dir = tempfile::tempdir().unwrap();
        let config = StorageConfig::Local {
            path: dir.path().to_string_lossy().to_string(),
        };
        let backend = StorageBackend::from_config(&config).unwrap();
        let manifest = Arc::new(ManifestManager::open(backend.clone()).await.unwrap());

        let (writer, processor) = WalWriter::new(backend.clone(), manifest.clone(), 1);

        // Spawn the batch processor
        let handle = tokio::spawn(processor.run());

        // Write some entries
        let entries = vec![
            Entry::new(Bytes::from("key1"), Bytes::from("value1"), 1),
            Entry::new(Bytes::from("key2"), Bytes::from("value2"), 2),
        ];

        writer.write("test-ns".into(), entries).await.unwrap();

        // Verify the WAL SST was written
        let state = manifest.current_state();
        let ns = state.namespaces.get("test-ns").unwrap();
        assert_eq!(ns.wal_ssts.len(), 1);
        assert_eq!(ns.wal_ssts[0].num_entries, 2);

        // Clean up
        drop(writer);
        let _ = handle.await;
    }
}
