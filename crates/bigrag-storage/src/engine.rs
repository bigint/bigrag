use bytes::Bytes;
use std::sync::Arc;
use tracing::info;

use bigrag_common::config::ServerConfig;

use crate::backend::StorageBackend;
use crate::cache::{BlockCache, DiskCache};
use crate::compaction::{CompactionConfig, CompactionScheduler};
use crate::manifest::ManifestManager;
use crate::memtable::{GetResult, MemTableManager};
use crate::sst::{Entry, SstReader};
use crate::wal::WalWriter;

/// The core storage engine. Coordinates memtable, WAL, SSTs, and cache.
pub struct StorageEngine {
    backend: StorageBackend,
    manifest: Arc<ManifestManager>,
    memtables: Arc<dashmap::DashMap<String, MemTableManager>>,
    cache: BlockCache,
    disk_cache: Option<DiskCache>,
    wal_writer: Arc<WalWriter>,
    writer_epoch: u64,
}

impl StorageEngine {
    pub async fn open(config: &ServerConfig) -> Result<(Self, EngineBackground), EngineError> {
        let backend = StorageBackend::from_config(&config.storage)
            .map_err(|e| EngineError::Init(format!("storage backend: {e}")))?;

        let manifest = Arc::new(
            ManifestManager::open(backend.clone())
                .await
                .map_err(|e| EngineError::Init(format!("manifest: {e}")))?,
        );

        // Claim writer epoch
        let writer_epoch = manifest
            .claim_writer_epoch()
            .await
            .map_err(|e| EngineError::Init(format!("epoch claim: {e}")))?;

        info!(writer_epoch, "storage engine initialized");

        let cache = BlockCache::new(
            config.cache.block_cache_size_mb,
            config.cache.metadata_cache_size_mb,
        );

        // Initialize NVMe/disk L2 cache if configured
        let disk_cache = if let Some(ref path) = config.cache.nvme_cache_path {
            match DiskCache::new(path, config.cache.nvme_cache_size_gb) {
                Ok(dc) => {
                    info!(path, size_gb = config.cache.nvme_cache_size_gb, "disk L2 cache enabled");
                    Some(dc)
                }
                Err(e) => {
                    tracing::warn!(path, error = %e, "failed to initialize disk cache, continuing without it");
                    None
                }
            }
        } else {
            None
        };

        let (wal_writer, wal_processor) =
            WalWriter::new(backend.clone(), manifest.clone(), writer_epoch);

        // Set up compaction
        let compaction = CompactionScheduler::new(
            backend.clone(),
            manifest.clone(),
            CompactionConfig::default(),
        );

        let memtables = Arc::new(dashmap::DashMap::new());

        let engine = Self {
            backend,
            manifest,
            memtables,
            cache,
            disk_cache,
            wal_writer: Arc::new(wal_writer),
            writer_epoch,
        };

        let background = EngineBackground {
            wal_processor,
            compaction,
        };

        Ok((engine, background))
    }

    /// Write entries to a namespace. Returns after durable persistence to WAL.
    pub async fn write(
        &self,
        namespace: &str,
        entries: Vec<Entry>,
    ) -> Result<usize, EngineError> {
        let count = entries.len();

        // Write to memtable for serving reads immediately
        let mgr = self.get_or_create_memtable(namespace);
        for entry in &entries {
            if entry.deleted {
                mgr.delete(entry.key.clone(), entry.timestamp);
            } else {
                mgr.put(entry.key.clone(), entry.value.clone(), entry.timestamp);
            }
        }

        // Write to WAL for durability
        self.wal_writer
            .write(namespace.to_string(), entries)
            .await
            .map_err(|e| EngineError::Write(format!("WAL write failed: {e}")))?;

        Ok(count)
    }

    /// Read a key from a namespace. Multi-tier read path:
    /// 1. Mutable MemTable
    /// 2. Immutable MemTables
    /// 3. WAL SSTs (L0, newest first)
    /// 4. Sorted Runs (compacted, newest first)
    pub async fn get(
        &self,
        namespace: &str,
        key: &[u8],
    ) -> Result<Option<Bytes>, EngineError> {
        // 1. Check memtable
        if let Some(mgr) = self.memtables.get(namespace) {
            match mgr.get(key) {
                Some(GetResult::Found(v)) => return Ok(Some(v)),
                Some(GetResult::Deleted) => return Ok(None),
                None => {}
            }
        }

        // 2-4. Check SSTs on storage
        let ns_state = match self.manifest.namespace_state(namespace) {
            Some(s) => s,
            None => return Ok(None),
        };

        // 3. WAL SSTs (L0, newest first — higher seq = newer)
        let mut wal_ssts = ns_state.wal_ssts.clone();
        wal_ssts.sort_by(|a, b| b.seq.cmp(&a.seq));

        for sst_meta in &wal_ssts {
            if let Some(value) = self.read_from_sst(sst_meta, key).await? {
                return Ok(Some(value));
            }
        }

        // 4. Sorted runs (newest first)
        let mut sorted_runs = ns_state.sorted_runs.clone();
        sorted_runs.sort_by(|a, b| {
            let a_max = a.ssts.iter().map(|s| s.seq).max().unwrap_or(0);
            let b_max = b.ssts.iter().map(|s| s.seq).max().unwrap_or(0);
            b_max.cmp(&a_max)
        });

        for run in &sorted_runs {
            for sst_meta in &run.ssts {
                if let Some(value) = self.read_from_sst(sst_meta, key).await? {
                    return Ok(Some(value));
                }
            }
        }

        Ok(None)
    }

    /// Scan all entries in a namespace (for query engine).
    pub async fn scan_namespace(
        &self,
        namespace: &str,
    ) -> Result<Vec<Entry>, EngineError> {
        let mut all_entries = Vec::new();

        // Memtable entries — scanned via SSTs that memtable flushes produce.
        // For fresh writes not yet flushed, the WAL SSTs cover them.

        // SST entries
        let ns_state = match self.manifest.namespace_state(namespace) {
            Some(s) => s,
            None => return Ok(vec![]),
        };

        // WAL SSTs
        for sst_meta in &ns_state.wal_ssts {
            let entries = self.scan_sst(sst_meta).await?;
            all_entries.extend(entries);
        }

        // Sorted runs
        for run in &ns_state.sorted_runs {
            for sst_meta in &run.ssts {
                let entries = self.scan_sst(sst_meta).await?;
                all_entries.extend(entries);
            }
        }

        // Sort by key, then deduplicate (keep newest)
        all_entries.sort_by(|a, b| a.key.cmp(&b.key).then(b.timestamp.cmp(&a.timestamp)));

        let mut deduped = Vec::new();
        let mut last_key: Option<Bytes> = None;
        for entry in all_entries {
            if last_key.as_ref() == Some(&entry.key) {
                continue;
            }
            last_key = Some(entry.key.clone());
            if !entry.deleted {
                deduped.push(entry);
            }
        }

        Ok(deduped)
    }

    async fn read_from_sst(
        &self,
        sst_meta: &crate::manifest::SstMeta,
        key: &[u8],
    ) -> Result<Option<Bytes>, EngineError> {
        // Quick key range check
        if let (Some(first), Some(last)) = (&sst_meta.first_key, &sst_meta.last_key) {
            if key < first.as_slice() || key > last.as_slice() {
                return Ok(None);
            }
        }

        // Try L2 disk cache before going to object storage
        let data = if let Some(ref dc) = self.disk_cache {
            if let Some(cached) = dc.get(&sst_meta.path) {
                cached
            } else {
                let fetched = self
                    .backend
                    .get(&sst_meta.path)
                    .await
                    .map_err(|e| EngineError::Read(format!("failed to read SST: {e}")))?;
                // Populate L2 cache on miss
                dc.put(&sst_meta.path, &fetched);
                fetched
            }
        } else {
            self.backend
                .get(&sst_meta.path)
                .await
                .map_err(|e| EngineError::Read(format!("failed to read SST: {e}")))?
        };

        let reader = SstReader::open(data)
            .ok_or_else(|| EngineError::Read("failed to parse SST".into()))?;

        Ok(reader.get(key))
    }

    async fn scan_sst(
        &self,
        sst_meta: &crate::manifest::SstMeta,
    ) -> Result<Vec<Entry>, EngineError> {
        // Try L2 disk cache before going to object storage
        let data = if let Some(ref dc) = self.disk_cache {
            if let Some(cached) = dc.get(&sst_meta.path) {
                cached
            } else {
                let fetched = self
                    .backend
                    .get(&sst_meta.path)
                    .await
                    .map_err(|e| EngineError::Read(format!("failed to read SST: {e}")))?;
                dc.put(&sst_meta.path, &fetched);
                fetched
            }
        } else {
            self.backend
                .get(&sst_meta.path)
                .await
                .map_err(|e| EngineError::Read(format!("failed to read SST: {e}")))?
        };

        let reader = SstReader::open(data)
            .ok_or_else(|| EngineError::Read("failed to parse SST".into()))?;

        Ok(reader.scan())
    }

    fn get_or_create_memtable(&self, namespace: &str) -> dashmap::mapref::one::Ref<String, MemTableManager> {
        if !self.memtables.contains_key(namespace) {
            self.memtables
                .insert(namespace.to_string(), MemTableManager::new(64));
        }
        self.memtables.get(namespace).unwrap()
    }

    pub fn manifest(&self) -> &Arc<ManifestManager> {
        &self.manifest
    }

    pub fn backend(&self) -> &StorageBackend {
        &self.backend
    }

    pub fn cache(&self) -> &BlockCache {
        &self.cache
    }
}

/// Background tasks that must be spawned separately.
pub struct EngineBackground {
    pub wal_processor: crate::wal::WalBatchProcessor,
    pub compaction: CompactionScheduler,
}

impl EngineBackground {
    pub fn spawn(self) -> Vec<tokio::task::JoinHandle<()>> {
        let mut handles = Vec::new();
        handles.push(tokio::spawn(self.wal_processor.run()));
        handles.push(tokio::spawn(self.compaction.run()));
        handles
    }
}

#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("initialization error: {0}")]
    Init(String),

    #[error("write error: {0}")]
    Write(String),

    #[error("read error: {0}")]
    Read(String),
}

#[cfg(test)]
mod tests {
    use super::*;
    use bigrag_common::config::{CacheConfig, CompactionConfig as CompConfig, StorageConfig, WalConfig};

    fn test_config(path: &str) -> ServerConfig {
        ServerConfig {
            host: "127.0.0.1".into(),
            port: 3000,
            metrics_port: 9090,
            max_connections: 10000,
            request_timeout_ms: 60000,
            max_request_body_mb: 512,
            storage: StorageConfig::Local {
                path: path.to_string(),
            },
            cache: CacheConfig::default(),
            wal: WalConfig::default(),
            compaction: CompConfig::default(),
        }
    }

    #[tokio::test]
    async fn test_engine_write_and_read() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(&dir.path().to_string_lossy());

        let (engine, background) = StorageEngine::open(&config).await.unwrap();
        let _handles = background.spawn();

        // Write entries
        let entries = vec![
            Entry::new(Bytes::from("key1"), Bytes::from("value1"), 1),
            Entry::new(Bytes::from("key2"), Bytes::from("value2"), 2),
        ];
        let count = engine.write("test-ns", entries).await.unwrap();
        assert_eq!(count, 2);

        // Read from memtable (fast path)
        let val = engine.get("test-ns", b"key1").await.unwrap();
        assert_eq!(val, Some(Bytes::from("value1")));

        // Missing key
        let val = engine.get("test-ns", b"missing").await.unwrap();
        assert!(val.is_none());
    }
}
