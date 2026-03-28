use bytes::Bytes;
use moka::future::Cache;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use tracing::debug;

/// Multi-tier read cache: in-memory block cache + metadata cache.
#[derive(Clone)]
pub struct BlockCache {
    /// LRU cache for data blocks keyed by (sst_path, block_offset).
    block_cache: Cache<CacheKey, Bytes>,
    /// Pinned cache for bloom filters and index blocks.
    metadata_cache: Cache<CacheKey, Bytes>,
    /// Hit/miss counters.
    stats: Arc<CacheStats>,
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub struct CacheKey {
    pub path: String,
    pub offset: u64,
    pub kind: CacheKeyKind,
}

#[derive(Debug, Clone, Hash, PartialEq, Eq)]
pub enum CacheKeyKind {
    DataBlock,
    BloomFilter,
    IndexBlock,
}

#[derive(Debug, Default)]
pub struct CacheStats {
    hits: std::sync::atomic::AtomicU64,
    misses: std::sync::atomic::AtomicU64,
}

impl CacheStats {
    pub fn record_hit(&self) {
        self.hits
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn record_miss(&self) {
        self.misses
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn hit_ratio(&self) -> f64 {
        let hits = self.hits.load(std::sync::atomic::Ordering::Relaxed);
        let misses = self.misses.load(std::sync::atomic::Ordering::Relaxed);
        let total = hits + misses;
        if total == 0 {
            0.0
        } else {
            hits as f64 / total as f64
        }
    }
}

impl BlockCache {
    pub fn new(block_cache_mb: u64, metadata_cache_mb: u64) -> Self {
        let block_cache = Cache::builder()
            .max_capacity(block_cache_mb * 1024 * 1024)
            .weigher(|_key: &CacheKey, value: &Bytes| -> u32 {
                value.len().try_into().unwrap_or(u32::MAX)
            })
            .build();

        let metadata_cache = Cache::builder()
            .max_capacity(metadata_cache_mb * 1024 * 1024)
            .weigher(|_key: &CacheKey, value: &Bytes| -> u32 {
                value.len().try_into().unwrap_or(u32::MAX)
            })
            .build();

        Self {
            block_cache,
            metadata_cache,
            stats: Arc::new(CacheStats::default()),
        }
    }

    /// Get a data block from cache.
    pub async fn get_block(&self, key: &CacheKey) -> Option<Bytes> {
        let result = self.block_cache.get(key).await;
        if result.is_some() {
            self.stats.record_hit();
        } else {
            self.stats.record_miss();
        }
        result
    }

    /// Insert a data block into cache.
    pub async fn insert_block(&self, key: CacheKey, data: Bytes) {
        self.block_cache.insert(key, data).await;
    }

    /// Get metadata (bloom filter or index block) from cache.
    pub async fn get_metadata(&self, key: &CacheKey) -> Option<Bytes> {
        let result = self.metadata_cache.get(key).await;
        if result.is_some() {
            self.stats.record_hit();
        } else {
            self.stats.record_miss();
        }
        result
    }

    /// Insert metadata into cache.
    pub async fn insert_metadata(&self, key: CacheKey, data: Bytes) {
        self.metadata_cache.insert(key, data).await;
    }

    /// Get the cache hit ratio.
    pub fn hit_ratio(&self) -> f64 {
        self.stats.hit_ratio()
    }

    /// Invalidate all entries for a given SST path.
    pub fn invalidate_sst(&self, path: &str) {
        self.block_cache.invalidate_all();
        self.metadata_cache.invalidate_all();
        debug!(path, "invalidated cache entries for SST");
    }
}

/// L2 cache tier: stores data on NVMe/SSD for faster access than object storage.
pub struct DiskCache {
    base_path: std::path::PathBuf,
    max_size_bytes: u64,
    current_size: AtomicU64,
}

impl DiskCache {
    pub fn new(path: &str, max_size_gb: u64) -> std::io::Result<Self> {
        std::fs::create_dir_all(path)?;
        Ok(Self {
            base_path: path.into(),
            max_size_bytes: max_size_gb * 1024 * 1024 * 1024,
            current_size: AtomicU64::new(0),
        })
    }

    fn cache_path(&self, key: &str) -> std::path::PathBuf {
        // Hash key to avoid path issues
        let hash = crc32fast::hash(key.as_bytes());
        let dir = self.base_path.join(format!("{:02x}", hash & 0xFF));
        dir.join(format!("{:08x}.cache", hash))
    }

    pub fn get(&self, key: &str) -> Option<Bytes> {
        let path = self.cache_path(key);
        std::fs::read(&path).ok().map(Bytes::from)
    }

    pub fn put(&self, key: &str, data: &[u8]) {
        if self.current_size.load(Ordering::Relaxed) + data.len() as u64 > self.max_size_bytes {
            return; // Skip if full (simple eviction: just stop caching)
        }
        let path = self.cache_path(key);
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if std::fs::write(&path, data).is_ok() {
            self.current_size.fetch_add(data.len() as u64, Ordering::Relaxed);
        }
    }

    pub fn remove(&self, key: &str) {
        let path = self.cache_path(key);
        if let Ok(meta) = std::fs::metadata(&path) {
            let size = meta.len();
            if std::fs::remove_file(&path).is_ok() {
                self.current_size.fetch_sub(size, Ordering::Relaxed);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_block_cache_hit_miss() {
        let cache = BlockCache::new(1, 1);

        let key = CacheKey {
            path: "test.sst".into(),
            offset: 0,
            kind: CacheKeyKind::DataBlock,
        };

        // Miss
        assert!(cache.get_block(&key).await.is_none());

        // Insert
        cache
            .insert_block(key.clone(), Bytes::from("block data"))
            .await;

        // Hit
        let data = cache.get_block(&key).await.unwrap();
        assert_eq!(data, Bytes::from("block data"));
    }

    #[tokio::test]
    async fn test_metadata_cache() {
        let cache = BlockCache::new(1, 1);

        let key = CacheKey {
            path: "test.sst".into(),
            offset: 0,
            kind: CacheKeyKind::BloomFilter,
        };

        cache
            .insert_metadata(key.clone(), Bytes::from("bloom data"))
            .await;

        let data = cache.get_metadata(&key).await.unwrap();
        assert_eq!(data, Bytes::from("bloom data"));
    }

    #[tokio::test]
    async fn test_hit_ratio() {
        let cache = BlockCache::new(1, 1);

        let key = CacheKey {
            path: "test.sst".into(),
            offset: 0,
            kind: CacheKeyKind::DataBlock,
        };

        // 1 miss
        cache.get_block(&key).await;
        // Insert and 1 hit
        cache
            .insert_block(key.clone(), Bytes::from("data"))
            .await;
        cache.get_block(&key).await;

        let ratio = cache.hit_ratio();
        assert!((ratio - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_disk_cache_put_get() {
        let dir = tempfile::tempdir().unwrap();
        let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

        // Miss
        assert!(cache.get("key1").is_none());

        // Put
        cache.put("key1", b"hello world");

        // Hit
        let data = cache.get("key1").unwrap();
        assert_eq!(data.as_ref(), b"hello world");
    }

    #[test]
    fn test_disk_cache_remove() {
        let dir = tempfile::tempdir().unwrap();
        let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

        cache.put("key1", b"data");
        assert!(cache.get("key1").is_some());

        cache.remove("key1");
        assert!(cache.get("key1").is_none());
    }

    #[test]
    fn test_disk_cache_size_limit() {
        let dir = tempfile::tempdir().unwrap();
        // 0 GB max = 0 bytes, nothing should be cached
        let cache = DiskCache::new(&dir.path().to_string_lossy(), 0).unwrap();

        cache.put("key1", b"data");
        assert!(cache.get("key1").is_none());
    }
}
