use bytes::Bytes;
use crossbeam_skiplist::SkipMap;
use parking_lot::RwLock;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};

use crate::sst::{Entry, SstBuilder, SstData, Compression};

/// Composite key for the skip list: (user_key, inverted_timestamp).
/// Inverted timestamp ensures newest entries come first for the same key.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct MemKey {
    key: Bytes,
    inv_ts: u64,
}

/// Value stored in the memtable.
#[derive(Debug, Clone)]
struct MemValue {
    value: Bytes,
    deleted: bool,
}

/// A concurrent in-memory sorted structure backed by a lock-free skip list.
pub struct MemTable {
    map: SkipMap<Bytes, MemValue>,
    size: AtomicUsize,
    max_timestamp: AtomicU64,
    entry_count: AtomicUsize,
}

impl MemTable {
    pub fn new() -> Self {
        Self {
            map: SkipMap::new(),
            size: AtomicUsize::new(0),
            max_timestamp: AtomicU64::new(0),
            entry_count: AtomicUsize::new(0),
        }
    }

    /// Insert or update a key-value pair.
    pub fn put(&self, key: Bytes, value: Bytes, _timestamp: u64) {
        let entry_size = key.len() + value.len() + 16;
        self.map.insert(
            key,
            MemValue {
                value,
                deleted: false,
            },
        );
        self.size.fetch_add(entry_size, Ordering::Relaxed);
        self.entry_count.fetch_add(1, Ordering::Relaxed);
        self.max_timestamp
            .fetch_max(_timestamp, Ordering::Relaxed);
    }

    /// Mark a key as deleted (tombstone).
    pub fn delete(&self, key: Bytes, timestamp: u64) {
        let entry_size = key.len() + 16;
        self.map.insert(
            key,
            MemValue {
                value: Bytes::new(),
                deleted: true,
            },
        );
        self.size.fetch_add(entry_size, Ordering::Relaxed);
        self.entry_count.fetch_add(1, Ordering::Relaxed);
        self.max_timestamp.fetch_max(timestamp, Ordering::Relaxed);
    }

    /// Get the value for a key.
    pub fn get(&self, key: &[u8]) -> Option<GetResult> {
        let key = Bytes::copy_from_slice(key);
        self.map.get(&key).map(|entry| {
            let val = entry.value();
            if val.deleted {
                GetResult::Deleted
            } else {
                GetResult::Found(val.value.clone())
            }
        })
    }

    /// Approximate size in bytes.
    pub fn size(&self) -> usize {
        self.size.load(Ordering::Relaxed)
    }

    /// Number of entries (including overwrites).
    pub fn entry_count(&self) -> usize {
        self.entry_count.load(Ordering::Relaxed)
    }

    /// Maximum timestamp seen.
    pub fn max_timestamp(&self) -> u64 {
        self.max_timestamp.load(Ordering::Relaxed)
    }

    /// Drain the memtable into sorted entries for SSTable building.
    pub fn drain_to_entries(&self) -> Vec<Entry> {
        let ts = self.max_timestamp.load(Ordering::Relaxed);
        let mut entries = Vec::with_capacity(self.entry_count.load(Ordering::Relaxed));
        for entry in self.map.iter() {
            let val = entry.value();
            if val.deleted {
                entries.push(Entry::tombstone(entry.key().clone(), ts));
            } else {
                entries.push(Entry::new(entry.key().clone(), val.value.clone(), ts));
            }
        }
        entries
    }

    /// Flush the memtable to an SSTable.
    pub fn flush(&self, compression: Compression) -> Option<SstData> {
        let entries = self.drain_to_entries();
        if entries.is_empty() {
            return None;
        }
        let mut builder = SstBuilder::new(compression);
        builder.add_all(entries);
        Some(builder.build())
    }
}

pub enum GetResult {
    Found(Bytes),
    Deleted,
}

/// Manages the active memtable and a queue of immutable memtables being flushed.
pub struct MemTableManager {
    active: RwLock<MemTable>,
    immutables: RwLock<Vec<MemTable>>,
    flush_threshold: usize,
}

impl MemTableManager {
    pub fn new(flush_threshold_mb: u64) -> Self {
        Self {
            active: RwLock::new(MemTable::new()),
            immutables: RwLock::new(Vec::new()),
            flush_threshold: (flush_threshold_mb as usize) * 1024 * 1024,
        }
    }

    /// Insert a key-value pair. Returns true if the active memtable needs flushing.
    pub fn put(&self, key: Bytes, value: Bytes, timestamp: u64) -> bool {
        let active = self.active.read();
        active.put(key, value, timestamp);
        active.size() >= self.flush_threshold
    }

    /// Mark a key as deleted. Returns true if active memtable needs flushing.
    pub fn delete(&self, key: Bytes, timestamp: u64) -> bool {
        let active = self.active.read();
        active.delete(key, timestamp);
        active.size() >= self.flush_threshold
    }

    /// Get from active memtable, then immutable memtables (newest first).
    pub fn get(&self, key: &[u8]) -> Option<GetResult> {
        // Check active first
        let result = self.active.read().get(key);
        if result.is_some() {
            return result;
        }

        // Check immutables newest-first
        let immutables = self.immutables.read();
        for mt in immutables.iter().rev() {
            let result = mt.get(key);
            if result.is_some() {
                return result;
            }
        }
        None
    }

    /// Rotate the active memtable to immutable, creating a new active.
    /// Returns the old memtable for flushing.
    pub fn rotate(&self) -> MemTable {
        let mut active = self.active.write();
        let old = std::mem::replace(&mut *active, MemTable::new());
        // We don't push to immutables here — the caller should flush and then
        // the MemTable is consumed. We keep a reference in immutables for reads
        // during the flush.
        old
    }

    /// Rotate and add to immutables list. Returns the immutable for flushing.
    pub fn rotate_for_flush(&self) -> Option<usize> {
        let old = self.rotate();
        if old.entry_count() == 0 {
            return None;
        }
        let mut immutables = self.immutables.write();
        let idx = immutables.len();
        immutables.push(old);
        Some(idx)
    }

    /// Remove a flushed immutable memtable.
    pub fn remove_immutable(&self, idx: usize) {
        let mut immutables = self.immutables.write();
        if idx < immutables.len() {
            immutables.remove(idx);
        }
    }

    /// Get the immutable memtable at an index for flushing.
    pub fn get_immutable(&self, idx: usize) -> Option<SstData> {
        let immutables = self.immutables.read();
        immutables.get(idx)?.flush(Compression::Lz4)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_memtable_put_get() {
        let mt = MemTable::new();
        mt.put(Bytes::from("key1"), Bytes::from("value1"), 1);
        mt.put(Bytes::from("key2"), Bytes::from("value2"), 2);

        match mt.get(b"key1") {
            Some(GetResult::Found(v)) => assert_eq!(v, Bytes::from("value1")),
            _ => panic!("expected Found"),
        }

        assert!(mt.get(b"missing").is_none());
    }

    #[test]
    fn test_memtable_delete() {
        let mt = MemTable::new();
        mt.put(Bytes::from("key1"), Bytes::from("value1"), 1);
        mt.delete(Bytes::from("key1"), 2);

        match mt.get(b"key1") {
            Some(GetResult::Deleted) => {}
            _ => panic!("expected Deleted"),
        }
    }

    #[test]
    fn test_memtable_overwrite() {
        let mt = MemTable::new();
        mt.put(Bytes::from("key1"), Bytes::from("old"), 1);
        mt.put(Bytes::from("key1"), Bytes::from("new"), 2);

        match mt.get(b"key1") {
            Some(GetResult::Found(v)) => assert_eq!(v, Bytes::from("new")),
            _ => panic!("expected new value"),
        }
    }

    #[test]
    fn test_memtable_flush() {
        let mt = MemTable::new();
        for i in 0..50u64 {
            mt.put(
                Bytes::from(format!("key_{i:04}")),
                Bytes::from(format!("val_{i}")),
                i,
            );
        }

        let sst = mt.flush(Compression::None).unwrap();
        assert_eq!(sst.num_entries, 50);
    }

    #[test]
    fn test_memtable_manager_basic() {
        let mgr = MemTableManager::new(1); // 1 MB threshold
        mgr.put(Bytes::from("k1"), Bytes::from("v1"), 1);
        mgr.put(Bytes::from("k2"), Bytes::from("v2"), 2);

        match mgr.get(b"k1") {
            Some(GetResult::Found(v)) => assert_eq!(v, Bytes::from("v1")),
            _ => panic!("expected Found"),
        }
    }

    #[test]
    fn test_memtable_drain_sorted() {
        let mt = MemTable::new();
        mt.put(Bytes::from("c"), Bytes::from("3"), 1);
        mt.put(Bytes::from("a"), Bytes::from("1"), 2);
        mt.put(Bytes::from("b"), Bytes::from("2"), 3);

        let entries = mt.drain_to_entries();
        assert_eq!(entries.len(), 3);
        // SkipMap iterates in sorted order
        assert_eq!(entries[0].key, Bytes::from("a"));
        assert_eq!(entries[1].key, Bytes::from("b"));
        assert_eq!(entries[2].key, Bytes::from("c"));
    }
}
