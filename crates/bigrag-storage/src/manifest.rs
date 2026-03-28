use bytes::Bytes;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::info;

use crate::backend::{BackendError, StorageBackend};

/// The persistent database state stored in manifests.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DbState {
    /// Monotonically increasing writer epoch for fencing.
    pub writer_epoch: u64,
    /// Compactor epoch (separate from writer).
    pub compactor_epoch: u64,
    /// Manifest sequence number.
    pub manifest_seq: u64,
    /// Next WAL sequence number.
    pub next_wal_seq: u64,
    /// Next SST sequence number.
    pub next_sst_seq: u64,
    /// Per-namespace SST inventory.
    pub namespaces: HashMap<String, NamespaceState>,
    /// Active snapshots (for reads during compaction).
    pub snapshots: Vec<Snapshot>,
}

impl Default for DbState {
    fn default() -> Self {
        Self {
            writer_epoch: 0,
            compactor_epoch: 0,
            manifest_seq: 0,
            next_wal_seq: 1,
            next_sst_seq: 1,
            namespaces: HashMap::new(),
            snapshots: Vec::new(),
        }
    }
}

/// Per-namespace state within the manifest.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NamespaceState {
    /// WAL SST files (L0, unsorted).
    pub wal_ssts: Vec<SstMeta>,
    /// Sorted runs from compaction.
    pub sorted_runs: Vec<SortedRun>,
    /// Schema definition (serialized).
    pub schema: Option<serde_json::Value>,
    /// Distance metric for vectors.
    pub distance_metric: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last write timestamp.
    pub updated_at: String,
}

/// Metadata about a single SST file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SstMeta {
    pub seq: u64,
    pub path: String,
    pub level: u32,
    pub size_bytes: u64,
    pub num_entries: u64,
    pub first_key: Option<Vec<u8>>,
    pub last_key: Option<Vec<u8>>,
    pub writer_epoch: u64,
}

/// A sorted run is a collection of SSTs in sorted, non-overlapping key order.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SortedRun {
    pub level: u32,
    pub ssts: Vec<SstMeta>,
}

/// A read snapshot for consistent reads during compaction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Snapshot {
    pub id: u64,
    pub manifest_seq: u64,
}

/// Manifest manager: reads, writes, and fences manifests on object storage.
pub struct ManifestManager {
    backend: StorageBackend,
    current: parking_lot::RwLock<DbState>,
}

impl ManifestManager {
    /// Load the latest manifest from storage, or create initial state.
    pub async fn open(backend: StorageBackend) -> Result<Self, ManifestError> {
        let state = Self::load_latest(&backend).await?;
        Ok(Self {
            backend,
            current: parking_lot::RwLock::new(state),
        })
    }

    /// Load the latest manifest. Returns default state if none exists.
    async fn load_latest(backend: &StorageBackend) -> Result<DbState, ManifestError> {
        let paths = backend.list("manifest/").await.map_err(|e| {
            ManifestError::Storage(format!("failed to list manifests: {e}"))
        })?;

        if paths.is_empty() {
            info!("no existing manifests found, starting fresh");
            return Ok(DbState::default());
        }

        // Find the latest manifest (highest sequence number)
        let latest_path = paths
            .iter()
            .filter(|p| p.ends_with(".manifest"))
            .max()
            .ok_or_else(|| ManifestError::Storage("no valid manifest files found".into()))?;

        let data = backend.get(latest_path).await.map_err(|e| {
            ManifestError::Storage(format!("failed to read manifest: {e}"))
        })?;

        let state: DbState = serde_json::from_slice(&data).map_err(|e| {
            ManifestError::Corrupted(format!("failed to parse manifest: {e}"))
        })?;

        info!(
            manifest_seq = state.manifest_seq,
            writer_epoch = state.writer_epoch,
            "loaded manifest"
        );

        Ok(state)
    }

    /// Claim writer epoch: increment and CAS-write a new manifest.
    /// Returns the new epoch. Fails if another writer has a higher epoch.
    pub async fn claim_writer_epoch(&self) -> Result<u64, ManifestError> {
        let mut state = self.current.write().clone();
        state.writer_epoch += 1;
        state.manifest_seq += 1;

        let path = StorageBackend::manifest_path(state.manifest_seq);
        let data = serde_json::to_vec_pretty(&state).map_err(|e| {
            ManifestError::Storage(format!("failed to serialize manifest: {e}"))
        })?;

        match self.backend.put_if_not_exists(&path, Bytes::from(data)).await {
            Ok(()) => {
                let epoch = state.writer_epoch;
                *self.current.write() = state;
                info!(epoch, "claimed writer epoch");
                Ok(epoch)
            }
            Err(BackendError::CasConflict(_)) => {
                // Another writer claimed this sequence. Reload and check epoch.
                let latest = Self::load_latest(&self.backend).await?;
                if latest.writer_epoch > state.writer_epoch {
                    Err(ManifestError::EpochFenced {
                        our_epoch: state.writer_epoch,
                        winner_epoch: latest.writer_epoch,
                    })
                } else {
                    // Race on same epoch — retry
                    Err(ManifestError::CasConflict)
                }
            }
            Err(e) => Err(ManifestError::Storage(format!(
                "failed to write manifest: {e}"
            ))),
        }
    }

    /// Commit a new manifest with updated state. Uses CAS.
    pub async fn commit<F>(&self, mutate: F) -> Result<(), ManifestError>
    where
        F: FnOnce(&mut DbState),
    {
        let mut state = self.current.write().clone();
        mutate(&mut state);
        state.manifest_seq += 1;

        let path = StorageBackend::manifest_path(state.manifest_seq);
        let data = serde_json::to_vec_pretty(&state).map_err(|e| {
            ManifestError::Storage(format!("failed to serialize manifest: {e}"))
        })?;

        match self.backend.put_if_not_exists(&path, Bytes::from(data)).await {
            Ok(()) => {
                *self.current.write() = state;
                Ok(())
            }
            Err(BackendError::CasConflict(_)) => Err(ManifestError::CasConflict),
            Err(e) => Err(ManifestError::Storage(format!(
                "failed to write manifest: {e}"
            ))),
        }
    }

    /// Get a snapshot of the current state.
    pub fn current_state(&self) -> DbState {
        self.current.read().clone()
    }

    /// Get the current writer epoch.
    pub fn writer_epoch(&self) -> u64 {
        self.current.read().writer_epoch
    }

    /// Allocate the next WAL sequence number.
    pub fn next_wal_seq(&self) -> u64 {
        let mut state = self.current.write();
        let seq = state.next_wal_seq;
        state.next_wal_seq += 1;
        seq
    }

    /// Allocate the next SST sequence number.
    pub fn next_sst_seq(&self) -> u64 {
        let mut state = self.current.write();
        let seq = state.next_sst_seq;
        state.next_sst_seq += 1;
        seq
    }

    /// Get namespace state.
    pub fn namespace_state(&self, namespace: &str) -> Option<NamespaceState> {
        self.current.read().namespaces.get(namespace).cloned()
    }

    /// List all namespace names.
    pub fn list_namespaces(&self) -> Vec<String> {
        self.current.read().namespaces.keys().cloned().collect()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ManifestError {
    #[error("storage error: {0}")]
    Storage(String),

    #[error("corrupted manifest: {0}")]
    Corrupted(String),

    #[error("CAS conflict: manifest was updated concurrently")]
    CasConflict,

    #[error("epoch fenced: our epoch {our_epoch} fenced by {winner_epoch}")]
    EpochFenced { our_epoch: u64, winner_epoch: u64 },
}

#[cfg(test)]
mod tests {
    use super::*;
    use bigrag_common::config::StorageConfig;

    #[tokio::test]
    async fn test_manifest_create_and_load() {
        let dir = tempfile::tempdir().unwrap();
        let config = StorageConfig::Local {
            path: dir.path().to_string_lossy().to_string(),
        };
        let backend = StorageBackend::from_config(&config).unwrap();

        // First open: creates fresh state
        let mgr = ManifestManager::open(backend.clone()).await.unwrap();
        assert_eq!(mgr.writer_epoch(), 0);

        // Claim epoch
        let epoch = mgr.claim_writer_epoch().await.unwrap();
        assert_eq!(epoch, 1);

        // Commit with state update
        mgr.commit(|state| {
            state.namespaces.insert(
                "test-ns".into(),
                NamespaceState {
                    wal_ssts: vec![],
                    sorted_runs: vec![],
                    schema: None,
                    distance_metric: Some("cosine_distance".into()),
                    created_at: "2026-01-01T00:00:00Z".into(),
                    updated_at: "2026-01-01T00:00:00Z".into(),
                },
            );
        })
        .await
        .unwrap();

        // Reopen and verify state persisted
        let mgr2 = ManifestManager::open(backend).await.unwrap();
        assert_eq!(mgr2.writer_epoch(), 1);
        assert!(mgr2.namespace_state("test-ns").is_some());
    }

    #[tokio::test]
    async fn test_epoch_fencing() {
        let dir = tempfile::tempdir().unwrap();
        let config = StorageConfig::Local {
            path: dir.path().to_string_lossy().to_string(),
        };
        let backend = StorageBackend::from_config(&config).unwrap();

        let mgr1 = ManifestManager::open(backend.clone()).await.unwrap();
        let mgr2 = ManifestManager::open(backend).await.unwrap();

        // Writer 1 claims epoch 1
        mgr1.claim_writer_epoch().await.unwrap();
        // Writer 2 tries to claim — should get CasConflict or EpochFenced
        let result = mgr2.claim_writer_epoch().await;
        assert!(result.is_err());
    }

    #[test]
    fn test_dbstate_serialization() {
        let state = DbState {
            writer_epoch: 5,
            compactor_epoch: 2,
            manifest_seq: 10,
            next_wal_seq: 100,
            next_sst_seq: 50,
            namespaces: HashMap::new(),
            snapshots: vec![],
        };

        let json = serde_json::to_string_pretty(&state).unwrap();
        let deserialized: DbState = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.writer_epoch, 5);
        assert_eq!(deserialized.manifest_seq, 10);
    }
}
