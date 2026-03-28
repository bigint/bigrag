//! Integration tests for NVMe/Disk L2 cache.
//! Run with: cargo test --test disk_cache_integration -p bigrag-storage

use bigrag_storage::cache::DiskCache;

#[test]
fn test_disk_cache_roundtrip() {
    let dir = tempfile::tempdir().unwrap();
    let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

    // Write several entries
    for i in 0..100 {
        let key = format!("sst/namespace/{i:04}.sst");
        let data = format!("block data for sst {i}");
        cache.put(&key, data.as_bytes());
    }

    // Read them back
    for i in 0..100 {
        let key = format!("sst/namespace/{i:04}.sst");
        let expected = format!("block data for sst {i}");
        let data = cache.get(&key).expect("cache miss");
        assert_eq!(data.as_ref(), expected.as_bytes());
    }
}

#[test]
fn test_disk_cache_remove_frees_space() {
    let dir = tempfile::tempdir().unwrap();
    let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

    cache.put("key-a", b"some data");
    assert!(cache.get("key-a").is_some());

    cache.remove("key-a");
    assert!(cache.get("key-a").is_none());
}

#[test]
fn test_disk_cache_overwrite() {
    let dir = tempfile::tempdir().unwrap();
    let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

    cache.put("key-x", b"version1");
    assert_eq!(cache.get("key-x").unwrap().as_ref(), b"version1");

    // Overwrite with new data
    cache.put("key-x", b"version2");
    assert_eq!(cache.get("key-x").unwrap().as_ref(), b"version2");
}

#[test]
fn test_disk_cache_nonexistent_key() {
    let dir = tempfile::tempdir().unwrap();
    let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

    assert!(cache.get("does-not-exist").is_none());
}

#[test]
fn test_disk_cache_remove_nonexistent() {
    let dir = tempfile::tempdir().unwrap();
    let cache = DiskCache::new(&dir.path().to_string_lossy(), 1).unwrap();

    // Should not panic
    cache.remove("does-not-exist");
}
