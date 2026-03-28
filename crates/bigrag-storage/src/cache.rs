use bytes::Bytes;
use moka::future::Cache;
use std::sync::Arc;
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
}
