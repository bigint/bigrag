use std::sync::Arc;
use tokio::time::{Duration, interval};
use tracing::{debug, info, warn};

use crate::backend::StorageBackend;
use crate::manifest::{ManifestManager, SstMeta, SortedRun};
use crate::sst::{Compression, Entry, SstBuilder, SstReader};

/// Tiered compaction scheduler.
///
/// WAL SSTs (L0) are compacted into larger sorted runs at higher levels.
/// Uses size-tiered strategy: when enough SSTs accumulate at a level,
/// merge them into the next level.
pub struct CompactionScheduler {
    backend: StorageBackend,
    manifest: Arc<ManifestManager>,
    config: CompactionConfig,
}

pub struct CompactionConfig {
    /// Number of L0 SSTs that trigger compaction.
    pub l0_compaction_trigger: usize,
    /// Size ratio for tiered compaction.
    pub size_ratio: f64,
    /// Maximum number of levels.
    pub max_levels: u32,
    /// Compression for compacted SSTs.
    pub compression: Compression,
}

impl Default for CompactionConfig {
    fn default() -> Self {
        Self {
            l0_compaction_trigger: 4,
            size_ratio: 4.0,
            max_levels: 7,
            compression: Compression::Zstd,
        }
    }
}

impl CompactionScheduler {
    pub fn new(
        backend: StorageBackend,
        manifest: Arc<ManifestManager>,
        config: CompactionConfig,
    ) -> Self {
        Self {
            backend,
            manifest,
            config,
        }
    }

    /// Run the compaction loop. Should be spawned as a background task.
    pub async fn run(self) {
        let mut tick = interval(Duration::from_secs(5));
        loop {
            tick.tick().await;
            let namespaces = self.manifest.list_namespaces();
            for ns in namespaces {
                if let Err(e) = self.maybe_compact(&ns).await {
                    warn!(namespace = %ns, error = %e, "compaction failed");
                }
            }
        }
    }

    async fn maybe_compact(&self, namespace: &str) -> Result<(), CompactionError> {
        let ns_state = self
            .manifest
            .namespace_state(namespace)
            .ok_or_else(|| CompactionError::NamespaceNotFound(namespace.to_string()))?;

        // Check if L0 needs compaction
        if ns_state.wal_ssts.len() >= self.config.l0_compaction_trigger {
            info!(
                namespace,
                l0_count = ns_state.wal_ssts.len(),
                "triggering L0 compaction"
            );
            self.compact_l0(namespace, &ns_state.wal_ssts).await?;
        }

        Ok(())
    }

    /// Compact L0 (WAL) SSTs into a sorted run.
    async fn compact_l0(
        &self,
        namespace: &str,
        wal_ssts: &[SstMeta],
    ) -> Result<(), CompactionError> {
        // Read all entries from all WAL SSTs
        let mut all_entries: Vec<Entry> = Vec::new();

        for sst_meta in wal_ssts {
            let data = self
                .backend
                .get(&sst_meta.path)
                .await
                .map_err(|e| CompactionError::Storage(format!("failed to read SST: {e}")))?;

            let reader = SstReader::open(data)
                .ok_or_else(|| CompactionError::Storage("failed to parse SST".into()))?;

            all_entries.extend(reader.scan());
        }

        if all_entries.is_empty() {
            return Ok(());
        }

        // Sort and deduplicate: for same key, keep most recent (highest timestamp)
        all_entries.sort_by(|a, b| a.key.cmp(&b.key).then(b.timestamp.cmp(&a.timestamp)));

        let mut deduped: Vec<Entry> = Vec::new();
        let mut last_key: Option<bytes::Bytes> = None;
        for entry in all_entries {
            if last_key.as_ref() == Some(&entry.key) {
                continue; // Skip older versions
            }
            last_key = Some(entry.key.clone());
            if !entry.deleted {
                deduped.push(entry);
            }
            // Drop tombstones during compaction (data is gone)
        }

        // Build compacted SST
        let mut builder = SstBuilder::new(self.config.compression);
        builder.add_all(deduped);
        let sst = builder.build();

        // Write to compacted path
        let seq = self.manifest.next_sst_seq();
        let path = StorageBackend::compacted_path(namespace, seq);

        self.backend
            .put(&path, sst.data.clone())
            .await
            .map_err(|e| CompactionError::Storage(format!("failed to write compacted SST: {e}")))?;

        let new_sst_meta = SstMeta {
            seq,
            path: path.clone(),
            level: 1,
            size_bytes: sst.data.len() as u64,
            num_entries: sst.num_entries as u64,
            first_key: sst.first_key.as_ref().map(|k| k.to_vec()),
            last_key: sst.last_key.as_ref().map(|k| k.to_vec()),
            writer_epoch: self.manifest.writer_epoch(),
        };

        // Collect paths of old WAL SSTs to delete
        let old_paths: Vec<String> = wal_ssts.iter().map(|s| s.path.clone()).collect();

        // Update manifest: remove WAL SSTs, add sorted run
        self.manifest
            .commit(|state| {
                if let Some(ns) = state.namespaces.get_mut(namespace) {
                    // Remove compacted WAL SSTs
                    ns.wal_ssts
                        .retain(|s| !old_paths.contains(&s.path));

                    // Add new sorted run at level 1
                    ns.sorted_runs.push(SortedRun {
                        level: 1,
                        ssts: vec![new_sst_meta.clone()],
                    });
                }
            })
            .await
            .map_err(|e| CompactionError::Manifest(format!("{e}")))?;

        // Delete old WAL SSTs (best effort)
        for old_path in &old_paths {
            if let Err(e) = self.backend.delete(old_path).await {
                warn!(path = %old_path, error = %e, "failed to delete old WAL SST");
            }
        }

        info!(
            namespace,
            compacted = wal_ssts.len(),
            output_entries = sst.num_entries,
            output_bytes = sst.data.len(),
            "L0 compaction complete"
        );

        Ok(())
    }
}

#[derive(Debug, thiserror::Error)]
pub enum CompactionError {
    #[error("namespace not found: {0}")]
    NamespaceNotFound(String),

    #[error("storage error: {0}")]
    Storage(String),

    #[error("manifest error: {0}")]
    Manifest(String),
}
