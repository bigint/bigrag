use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    #[serde(default = "default_host")]
    pub host: String,
    #[serde(default = "default_port")]
    pub port: u16,
    #[serde(default = "default_metrics_port")]
    pub metrics_port: u16,
    #[serde(default = "default_max_connections")]
    pub max_connections: u32,
    #[serde(default = "default_request_timeout_ms")]
    pub request_timeout_ms: u64,
    #[serde(default = "default_max_request_body_mb")]
    pub max_request_body_mb: u64,
    pub storage: StorageConfig,
    #[serde(default)]
    pub cache: CacheConfig,
    #[serde(default)]
    pub wal: WalConfig,
    #[serde(default)]
    pub compaction: CompactionConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "backend")]
pub enum StorageConfig {
    #[serde(rename = "local")]
    Local { path: String },
    #[serde(rename = "s3")]
    S3 {
        bucket: String,
        region: String,
        prefix: Option<String>,
        endpoint: Option<String>,
    },
    #[serde(rename = "gcs")]
    Gcs {
        bucket: String,
        prefix: Option<String>,
    },
    #[serde(rename = "azure")]
    Azure {
        container: String,
        account: String,
        prefix: Option<String>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheConfig {
    #[serde(default = "default_block_cache_size")]
    pub block_cache_size_mb: u64,
    #[serde(default = "default_metadata_cache_size")]
    pub metadata_cache_size_mb: u64,
    #[serde(default)]
    pub nvme_cache_path: Option<String>,
    #[serde(default = "default_nvme_cache_size")]
    pub nvme_cache_size_gb: u64,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            block_cache_size_mb: default_block_cache_size(),
            metadata_cache_size_mb: default_metadata_cache_size(),
            nvme_cache_path: None,
            nvme_cache_size_gb: default_nvme_cache_size(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalConfig {
    #[serde(default = "default_batch_interval_ms")]
    pub batch_interval_ms: u64,
    #[serde(default = "default_memtable_size")]
    pub memtable_flush_size_mb: u64,
}

impl Default for WalConfig {
    fn default() -> Self {
        Self {
            batch_interval_ms: default_batch_interval_ms(),
            memtable_flush_size_mb: default_memtable_size(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompactionConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_size_ratio")]
    pub size_ratio: f64,
    #[serde(default = "default_max_levels")]
    pub max_levels: u32,
}

impl Default for CompactionConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            size_ratio: default_size_ratio(),
            max_levels: default_max_levels(),
        }
    }
}

fn default_host() -> String {
    "0.0.0.0".into()
}
fn default_port() -> u16 {
    3000
}
fn default_metrics_port() -> u16 {
    9090
}
fn default_max_connections() -> u32 {
    10000
}
fn default_request_timeout_ms() -> u64 {
    60000
}
fn default_max_request_body_mb() -> u64 {
    512
}
fn default_block_cache_size() -> u64 {
    256
}
fn default_metadata_cache_size() -> u64 {
    64
}
fn default_nvme_cache_size() -> u64 {
    10
}
fn default_batch_interval_ms() -> u64 {
    1000
}
fn default_memtable_size() -> u64 {
    64
}
use crate::default_true;

fn default_size_ratio() -> f64 {
    4.0
}
fn default_max_levels() -> u32 {
    7
}
