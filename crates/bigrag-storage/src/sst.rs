use bytes::{Buf, BufMut, Bytes, BytesMut};
use crc32fast::Hasher;
use std::collections::BTreeMap;

/// Default block size for SSTable data blocks.
pub const DEFAULT_BLOCK_SIZE: usize = 4096;

/// Magic bytes identifying an SSTable file.
const SST_MAGIC: &[u8; 4] = b"BRST";

/// SSTable format version.
const SST_VERSION: u32 = 1;

/// Compression codec used for a block.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Compression {
    None = 0,
    Lz4 = 1,
    Zstd = 2,
}

impl Compression {
    pub fn from_u8(v: u8) -> Option<Self> {
        match v {
            0 => Some(Self::None),
            1 => Some(Self::Lz4),
            2 => Some(Self::Zstd),
            _ => None,
        }
    }
}

/// A single key-value entry in an SSTable.
#[derive(Debug, Clone)]
pub struct Entry {
    pub key: Bytes,
    pub value: Bytes,
    pub timestamp: u64,
    pub deleted: bool,
}

impl Entry {
    pub fn new(key: Bytes, value: Bytes, timestamp: u64) -> Self {
        Self {
            key,
            value,
            timestamp,
            deleted: false,
        }
    }

    pub fn tombstone(key: Bytes, timestamp: u64) -> Self {
        Self {
            key,
            value: Bytes::new(),
            timestamp,
            deleted: true,
        }
    }

    /// Encoded size: 4 (key_len) + key + 4 (val_len) + val + 8 (timestamp) + 1 (deleted)
    pub fn encoded_size(&self) -> usize {
        4 + self.key.len() + 4 + self.value.len() + 8 + 1
    }

    pub fn encode(&self, buf: &mut BytesMut) {
        buf.put_u32(self.key.len() as u32);
        buf.put_slice(&self.key);
        buf.put_u32(self.value.len() as u32);
        buf.put_slice(&self.value);
        buf.put_u64(self.timestamp);
        buf.put_u8(if self.deleted { 1 } else { 0 });
    }

    pub fn decode(buf: &mut &[u8]) -> Option<Self> {
        if buf.remaining() < 4 {
            return None;
        }
        let key_len = buf.get_u32() as usize;
        if buf.remaining() < key_len {
            return None;
        }
        let key = Bytes::copy_from_slice(&buf[..key_len]);
        buf.advance(key_len);

        if buf.remaining() < 4 {
            return None;
        }
        let val_len = buf.get_u32() as usize;
        if buf.remaining() < val_len {
            return None;
        }
        let value = Bytes::copy_from_slice(&buf[..val_len]);
        buf.advance(val_len);

        if buf.remaining() < 9 {
            return None;
        }
        let timestamp = buf.get_u64();
        let deleted = buf.get_u8() != 0;

        Some(Self {
            key,
            value,
            timestamp,
            deleted,
        })
    }
}

/// Block index entry pointing to a data block within the SST.
#[derive(Debug, Clone)]
pub struct BlockIndexEntry {
    pub first_key: Bytes,
    pub last_key: Bytes,
    pub offset: u64,
    pub length: u32,
    pub num_entries: u32,
}

/// Bloom filter for point lookups.
#[derive(Debug, Clone)]
pub struct BloomFilter {
    bits: Vec<u64>,
    num_hashes: u32,
}

impl BloomFilter {
    pub fn new(num_keys: usize, false_positive_rate: f64) -> Self {
        let num_bits = optimal_num_bits(num_keys, false_positive_rate);
        let num_words = (num_bits + 63) / 64;
        let num_hashes = optimal_num_hashes(num_bits, num_keys);
        Self {
            bits: vec![0u64; num_words],
            num_hashes,
        }
    }

    pub fn insert(&mut self, key: &[u8]) {
        let (h1, h2) = double_hash(key);
        for i in 0..self.num_hashes {
            let idx = combined_hash(h1, h2, i) % (self.bits.len() as u64 * 64);
            self.bits[(idx / 64) as usize] |= 1 << (idx % 64);
        }
    }

    pub fn may_contain(&self, key: &[u8]) -> bool {
        let (h1, h2) = double_hash(key);
        for i in 0..self.num_hashes {
            let idx = combined_hash(h1, h2, i) % (self.bits.len() as u64 * 64);
            if self.bits[(idx / 64) as usize] & (1 << (idx % 64)) == 0 {
                return false;
            }
        }
        true
    }

    pub fn encode(&self) -> Bytes {
        let mut buf = BytesMut::with_capacity(4 + 4 + self.bits.len() * 8);
        buf.put_u32(self.num_hashes);
        buf.put_u32(self.bits.len() as u32);
        for &word in &self.bits {
            buf.put_u64(word);
        }
        buf.freeze()
    }

    pub fn decode(data: &[u8]) -> Option<Self> {
        let mut buf = data;
        if buf.remaining() < 8 {
            return None;
        }
        let num_hashes = buf.get_u32();
        let num_words = buf.get_u32() as usize;
        if buf.remaining() < num_words * 8 {
            return None;
        }
        let mut bits = Vec::with_capacity(num_words);
        for _ in 0..num_words {
            bits.push(buf.get_u64());
        }
        Some(Self { bits, num_hashes })
    }
}

fn optimal_num_bits(n: usize, fp: f64) -> usize {
    let ln2 = std::f64::consts::LN_2;
    let bits = -(n as f64 * fp.ln()) / (ln2 * ln2);
    bits.ceil() as usize
}

fn optimal_num_hashes(num_bits: usize, num_keys: usize) -> u32 {
    let k = (num_bits as f64 / num_keys as f64) * std::f64::consts::LN_2;
    std::cmp::max(1, k.round() as u32)
}

fn double_hash(key: &[u8]) -> (u64, u64) {
    let mut hasher1 = Hasher::new();
    hasher1.update(key);
    let h1 = hasher1.finalize() as u64;

    let mut hasher2 = Hasher::new();
    hasher2.update(key);
    hasher2.update(&[0x9e, 0x37, 0x79, 0xb9]);
    let h2 = hasher2.finalize() as u64;

    (h1, h2)
}

fn combined_hash(h1: u64, h2: u64, i: u32) -> u64 {
    h1.wrapping_add((i as u64).wrapping_mul(h2))
}

/// Builds an SSTable from sorted entries.
pub struct SstBuilder {
    entries: Vec<Entry>,
    block_size: usize,
    compression: Compression,
}

impl SstBuilder {
    pub fn new(compression: Compression) -> Self {
        Self {
            entries: Vec::new(),
            block_size: DEFAULT_BLOCK_SIZE,
            compression,
        }
    }

    pub fn with_block_size(mut self, block_size: usize) -> Self {
        self.block_size = block_size;
        self
    }

    pub fn add(&mut self, entry: Entry) {
        self.entries.push(entry);
    }

    pub fn add_all(&mut self, entries: impl IntoIterator<Item = Entry>) {
        self.entries.extend(entries);
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn num_entries(&self) -> usize {
        self.entries.len()
    }

    /// Build the SSTable bytes.
    pub fn build(mut self) -> SstData {
        // Sort entries by key, then by timestamp descending (most recent first)
        self.entries
            .sort_by(|a, b| a.key.cmp(&b.key).then(b.timestamp.cmp(&a.timestamp)));

        // Build bloom filter
        let mut bloom = BloomFilter::new(self.entries.len().max(1), 0.01);
        for entry in &self.entries {
            bloom.insert(&entry.key);
        }

        // Split into blocks
        let mut blocks: Vec<(Bytes, Bytes, Bytes, u32)> = Vec::new(); // (first_key, last_key, data, num_entries)
        let mut current_block = BytesMut::new();
        let mut block_first_key: Option<Bytes> = None;
        let mut block_last_key: Option<Bytes> = None;
        let mut block_count: u32 = 0;

        for entry in &self.entries {
            if block_first_key.is_none() {
                block_first_key = Some(entry.key.clone());
            }
            block_last_key = Some(entry.key.clone());
            entry.encode(&mut current_block);
            block_count += 1;

            if current_block.len() >= self.block_size {
                let data = current_block.freeze();
                blocks.push((
                    block_first_key.take().unwrap(),
                    block_last_key.take().unwrap(),
                    data,
                    block_count,
                ));
                current_block = BytesMut::new();
                block_count = 0;
            }
        }

        // Flush remaining
        if !current_block.is_empty() {
            let data = current_block.freeze();
            blocks.push((
                block_first_key.unwrap(),
                block_last_key.unwrap(),
                data,
                block_count,
            ));
        }

        // Assemble SST file: header + data blocks + block index + bloom filter + footer
        let mut output = BytesMut::new();

        // Header: magic (4) + version (4) + num_blocks (4) + compression (1)
        output.put_slice(SST_MAGIC);
        output.put_u32(SST_VERSION);
        output.put_u32(blocks.len() as u32);
        output.put_u8(self.compression as u8);

        let header_size = output.len();

        // Data blocks (optionally compressed)
        let mut index_entries = Vec::new();
        for (first_key, last_key, raw_data, num_entries) in &blocks {
            let block_offset = output.len() as u64;
            let compressed = compress_block(&raw_data, self.compression);
            let block_len = compressed.len() as u32;

            // Block: compressed_len (4) + data + crc32 (4)
            let mut block_hasher = Hasher::new();
            block_hasher.update(&compressed);
            let crc = block_hasher.finalize();

            output.put_u32(block_len);
            output.put_slice(&compressed);
            output.put_u32(crc);

            index_entries.push(BlockIndexEntry {
                first_key: first_key.clone(),
                last_key: last_key.clone(),
                offset: block_offset,
                length: block_len + 8, // +8 for compressed_len(4) and crc(4)
                num_entries: *num_entries,
            });
        }

        // Block index
        let index_offset = output.len() as u64;
        output.put_u32(index_entries.len() as u32);
        for entry in &index_entries {
            output.put_u32(entry.first_key.len() as u32);
            output.put_slice(&entry.first_key);
            output.put_u32(entry.last_key.len() as u32);
            output.put_slice(&entry.last_key);
            output.put_u64(entry.offset);
            output.put_u32(entry.length);
            output.put_u32(entry.num_entries);
        }

        // Bloom filter
        let bloom_offset = output.len() as u64;
        let bloom_data = bloom.encode();
        output.put_u32(bloom_data.len() as u32);
        output.put_slice(&bloom_data);

        // Footer: index_offset (8) + bloom_offset (8) + total_entries (8) + magic (4)
        output.put_u64(index_offset);
        output.put_u64(bloom_offset);
        output.put_u64(self.entries.len() as u64);
        output.put_slice(SST_MAGIC);

        let first_key = self.entries.first().map(|e| e.key.clone());
        let last_key = self.entries.last().map(|e| e.key.clone());

        SstData {
            data: output.freeze(),
            num_entries: self.entries.len(),
            first_key,
            last_key,
            index_entries,
            bloom,
        }
    }
}

/// Result of building an SSTable.
pub struct SstData {
    pub data: Bytes,
    pub num_entries: usize,
    pub first_key: Option<Bytes>,
    pub last_key: Option<Bytes>,
    pub index_entries: Vec<BlockIndexEntry>,
    pub bloom: BloomFilter,
}

/// SSTable reader for querying an SSTable from bytes.
pub struct SstReader {
    data: Bytes,
    index_entries: Vec<BlockIndexEntry>,
    bloom: BloomFilter,
    compression: Compression,
    total_entries: u64,
}

impl SstReader {
    pub fn open(data: Bytes) -> Option<Self> {
        if data.len() < 28 {
            return None; // minimum: header(13) + footer(28)
        }

        // Verify footer magic
        let footer_magic = &data[data.len() - 4..];
        if footer_magic != SST_MAGIC {
            return None;
        }

        // Read footer
        let mut footer = &data[data.len() - 28..];
        let index_offset = footer.get_u64() as usize;
        let bloom_offset = footer.get_u64() as usize;
        let total_entries = footer.get_u64();

        // Read header
        let mut header = &data[..13];
        let magic = &header[..4];
        if magic != SST_MAGIC {
            return None;
        }
        header.advance(4);
        let _version = header.get_u32();
        let num_blocks = header.get_u32();
        let compression = Compression::from_u8(header.get_u8())?;

        // Parse block index
        let mut idx_reader = &data[index_offset..bloom_offset];
        let idx_count = idx_reader.get_u32();
        if idx_count != num_blocks {
            return None;
        }
        let mut index_entries = Vec::with_capacity(idx_count as usize);
        for _ in 0..idx_count {
            let fk_len = idx_reader.get_u32() as usize;
            let first_key = Bytes::copy_from_slice(&idx_reader[..fk_len]);
            idx_reader.advance(fk_len);
            let lk_len = idx_reader.get_u32() as usize;
            let last_key = Bytes::copy_from_slice(&idx_reader[..lk_len]);
            idx_reader.advance(lk_len);
            let offset = idx_reader.get_u64();
            let length = idx_reader.get_u32();
            let num_entries = idx_reader.get_u32();
            index_entries.push(BlockIndexEntry {
                first_key,
                last_key,
                offset,
                length,
                num_entries,
            });
        }

        // Parse bloom filter
        let mut bloom_reader = &data[bloom_offset..data.len() - 28];
        let bloom_len = bloom_reader.get_u32() as usize;
        let bloom = BloomFilter::decode(&bloom_reader[..bloom_len])?;

        Some(Self {
            data,
            index_entries,
            bloom,
            compression,
            total_entries,
        })
    }

    /// Check bloom filter for a key.
    pub fn may_contain(&self, key: &[u8]) -> bool {
        self.bloom.may_contain(key)
    }

    pub fn total_entries(&self) -> u64 {
        self.total_entries
    }

    /// Get the value for a key. Returns the most recent non-tombstone entry.
    pub fn get(&self, key: &[u8]) -> Option<Bytes> {
        if !self.may_contain(key) {
            return None;
        }

        let target = Bytes::copy_from_slice(key);
        // Binary search for the block that may contain the key
        let block_idx = self.index_entries.partition_point(|e| e.last_key < target);
        if block_idx >= self.index_entries.len() {
            return None;
        }

        let block_entry = &self.index_entries[block_idx];
        if target < block_entry.first_key {
            return None;
        }

        // Read and scan the block
        let entries = self.read_block(block_entry)?;
        for entry in entries {
            if entry.key == target {
                if entry.deleted {
                    return None;
                }
                return Some(entry.value);
            }
        }
        None
    }

    /// Scan all entries in order.
    pub fn scan(&self) -> Vec<Entry> {
        let mut all_entries = Vec::with_capacity(self.total_entries as usize);
        for block_entry in &self.index_entries {
            if let Some(entries) = self.read_block(block_entry) {
                all_entries.extend(entries);
            }
        }
        all_entries
    }

    /// Scan entries in a key range [start, end).
    pub fn scan_range(&self, start: &[u8], end: &[u8]) -> Vec<Entry> {
        let start_key = Bytes::copy_from_slice(start);
        let end_key = Bytes::copy_from_slice(end);
        let mut results = Vec::new();

        for block_entry in &self.index_entries {
            // Skip blocks entirely before our range
            if block_entry.last_key < start_key {
                continue;
            }
            // Stop at blocks entirely after our range
            if block_entry.first_key >= end_key {
                break;
            }

            if let Some(entries) = self.read_block(block_entry) {
                for entry in entries {
                    if entry.key >= start_key && entry.key < end_key {
                        results.push(entry);
                    }
                }
            }
        }
        results
    }

    fn read_block(&self, idx: &BlockIndexEntry) -> Option<Vec<Entry>> {
        let offset = idx.offset as usize;
        let mut reader = &self.data[offset..];

        let compressed_len = reader.get_u32() as usize;
        let compressed = &reader[..compressed_len];
        reader.advance(compressed_len);
        let stored_crc = reader.get_u32();

        // Verify CRC
        let mut hasher = Hasher::new();
        hasher.update(compressed);
        if hasher.finalize() != stored_crc {
            return None;
        }

        let decompressed = decompress_block(compressed, self.compression)?;
        let mut entries = Vec::new();
        let mut cursor = decompressed.as_slice();
        while !cursor.is_empty() {
            if let Some(entry) = Entry::decode(&mut cursor) {
                entries.push(entry);
            } else {
                break;
            }
        }
        Some(entries)
    }
}

fn compress_block(data: &[u8], compression: Compression) -> Vec<u8> {
    match compression {
        Compression::None => data.to_vec(),
        Compression::Lz4 => lz4_flex::compress_prepend_size(data),
        Compression::Zstd => zstd::encode_all(data, 3).unwrap_or_else(|_| data.to_vec()),
    }
}

fn decompress_block(data: &[u8], compression: Compression) -> Option<Vec<u8>> {
    match compression {
        Compression::None => Some(data.to_vec()),
        Compression::Lz4 => lz4_flex::decompress_size_prepended(data).ok(),
        Compression::Zstd => zstd::decode_all(data).ok(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entry_roundtrip() {
        let entry = Entry::new(Bytes::from("key1"), Bytes::from("value1"), 100);
        let mut buf = BytesMut::new();
        entry.encode(&mut buf);
        let decoded = Entry::decode(&mut buf.freeze().as_ref()).unwrap();
        assert_eq!(decoded.key, entry.key);
        assert_eq!(decoded.value, entry.value);
        assert_eq!(decoded.timestamp, entry.timestamp);
        assert!(!decoded.deleted);
    }

    #[test]
    fn test_tombstone() {
        let entry = Entry::tombstone(Bytes::from("deleted_key"), 200);
        let mut buf = BytesMut::new();
        entry.encode(&mut buf);
        let decoded = Entry::decode(&mut buf.freeze().as_ref()).unwrap();
        assert!(decoded.deleted);
        assert!(decoded.value.is_empty());
    }

    #[test]
    fn test_bloom_filter() {
        let mut bloom = BloomFilter::new(100, 0.01);
        bloom.insert(b"hello");
        bloom.insert(b"world");

        assert!(bloom.may_contain(b"hello"));
        assert!(bloom.may_contain(b"world"));
        // May have false positives, but should rarely
    }

    #[test]
    fn test_bloom_roundtrip() {
        let mut bloom = BloomFilter::new(100, 0.01);
        bloom.insert(b"test_key");

        let encoded = bloom.encode();
        let decoded = BloomFilter::decode(&encoded).unwrap();
        assert!(decoded.may_contain(b"test_key"));
    }

    #[test]
    fn test_sst_build_and_read_no_compression() {
        let mut builder = SstBuilder::new(Compression::None);
        for i in 0..100u64 {
            let key = format!("key_{i:04}");
            let val = format!("value_{i}");
            builder.add(Entry::new(
                Bytes::from(key),
                Bytes::from(val),
                i,
            ));
        }

        let sst = builder.build();
        let reader = SstReader::open(sst.data).unwrap();
        assert_eq!(reader.total_entries(), 100);

        // Point lookup
        let val = reader.get(b"key_0042").unwrap();
        assert_eq!(val, Bytes::from("value_42"));

        // Missing key
        assert!(reader.get(b"missing").is_none());
    }

    #[test]
    fn test_sst_with_lz4() {
        let mut builder = SstBuilder::new(Compression::Lz4);
        for i in 0..50u64 {
            let key = format!("k{i:06}");
            let val = format!("v{i}");
            builder.add(Entry::new(Bytes::from(key), Bytes::from(val), i));
        }

        let sst = builder.build();
        let reader = SstReader::open(sst.data).unwrap();
        assert_eq!(reader.total_entries(), 50);

        let val = reader.get(b"k000025").unwrap();
        assert_eq!(val, Bytes::from("v25"));
    }

    #[test]
    fn test_sst_with_zstd() {
        let mut builder = SstBuilder::new(Compression::Zstd);
        for i in 0..50u64 {
            let key = format!("k{i:06}");
            let val = format!("v{i}");
            builder.add(Entry::new(Bytes::from(key), Bytes::from(val), i));
        }

        let sst = builder.build();
        let reader = SstReader::open(sst.data).unwrap();
        let val = reader.get(b"k000010").unwrap();
        assert_eq!(val, Bytes::from("v10"));
    }

    #[test]
    fn test_sst_tombstone_hides_value() {
        let mut builder = SstBuilder::new(Compression::None);
        builder.add(Entry::new(Bytes::from("key"), Bytes::from("old"), 1));
        builder.add(Entry::tombstone(Bytes::from("key"), 2));

        let sst = builder.build();
        let reader = SstReader::open(sst.data).unwrap();
        // Tombstone (ts=2) is more recent, so key should not be found
        assert!(reader.get(b"key").is_none());
    }

    #[test]
    fn test_sst_scan_range() {
        let mut builder = SstBuilder::new(Compression::None);
        for i in 0..100u64 {
            let key = format!("key_{i:04}");
            builder.add(Entry::new(Bytes::from(key), Bytes::from("v"), i));
        }

        let sst = builder.build();
        let reader = SstReader::open(sst.data).unwrap();
        let range = reader.scan_range(b"key_0020", b"key_0030");
        assert_eq!(range.len(), 10);
        assert_eq!(range[0].key, Bytes::from("key_0020"));
        assert_eq!(range[9].key, Bytes::from("key_0029"));
    }
}
