use bigrag_common::config::StorageConfig;
use bytes::Bytes;
use object_store::path::Path;
use object_store::{
    ObjectStore, PutMode, PutOptions, PutPayload,
    local::LocalFileSystem,
    aws::AmazonS3Builder,
    gcp::GoogleCloudStorageBuilder,
    azure::MicrosoftAzureBuilder,
};
use std::sync::Arc;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum BackendError {
    #[error("object store error: {0}")]
    ObjectStore(#[from] object_store::Error),

    #[error("CAS conflict: object already exists at {0}")]
    CasConflict(String),
}

pub type BackendResult<T> = Result<T, BackendError>;

/// Storage backend wrapping object_store with bigRAG-specific path conventions.
#[derive(Clone)]
pub struct StorageBackend {
    store: Arc<dyn ObjectStore>,
    prefix: String,
}

impl StorageBackend {
    pub fn from_config(config: &StorageConfig) -> BackendResult<Self> {
        match config {
            StorageConfig::Local { path } => {
                std::fs::create_dir_all(path).map_err(|e| {
                    BackendError::ObjectStore(object_store::Error::Generic {
                        store: "local",
                        source: Box::new(e),
                    })
                })?;
                let store = LocalFileSystem::new_with_prefix(path)?;
                Ok(Self {
                    store: Arc::new(store),
                    prefix: String::new(),
                })
            }
            StorageConfig::S3 {
                bucket,
                region,
                prefix,
            } => {
                let store = AmazonS3Builder::new()
                    .with_bucket_name(bucket)
                    .with_region(region)
                    .build()?;
                Ok(Self {
                    store: Arc::new(store),
                    prefix: prefix.clone().unwrap_or_default(),
                })
            }
            StorageConfig::Gcs { bucket, prefix } => {
                let store = GoogleCloudStorageBuilder::new()
                    .with_bucket_name(bucket)
                    .build()?;
                Ok(Self {
                    store: Arc::new(store),
                    prefix: prefix.clone().unwrap_or_default(),
                })
            }
            StorageConfig::Azure {
                container,
                account,
                prefix,
            } => {
                let store = MicrosoftAzureBuilder::new()
                    .with_container_name(container)
                    .with_account(account)
                    .build()?;
                Ok(Self {
                    store: Arc::new(store),
                    prefix: prefix.clone().unwrap_or_default(),
                })
            }
        }
    }

    fn full_path(&self, path: &str) -> Path {
        if self.prefix.is_empty() {
            Path::from(path)
        } else {
            Path::from(format!("{}/{}", self.prefix, path))
        }
    }

    /// Write data to a path. Overwrites if exists.
    pub async fn put(&self, path: &str, data: Bytes) -> BackendResult<()> {
        let location = self.full_path(path);
        self.store.put(&location, PutPayload::from(data)).await?;
        Ok(())
    }

    /// Write data with CAS: fails if the object already exists.
    /// Used for manifest updates and writer epoch fencing.
    pub async fn put_if_not_exists(&self, path: &str, data: Bytes) -> BackendResult<()> {
        let location = self.full_path(path);
        let opts = PutOptions {
            mode: PutMode::Create,
            ..Default::default()
        };
        match self.store.put_opts(&location, PutPayload::from(data), opts).await {
            Ok(_) => Ok(()),
            Err(object_store::Error::AlreadyExists { path, .. }) => {
                Err(BackendError::CasConflict(path))
            }
            Err(e) => Err(BackendError::ObjectStore(e)),
        }
    }

    /// Read data from a path.
    pub async fn get(&self, path: &str) -> BackendResult<Bytes> {
        let location = self.full_path(path);
        let result = self.store.get(&location).await?;
        let bytes = result.bytes().await?;
        Ok(bytes)
    }

    /// Read a byte range from a path.
    pub async fn get_range(&self, path: &str, range: std::ops::Range<u64>) -> BackendResult<Bytes> {
        let location = self.full_path(path);
        let bytes = self.store.get_range(&location, range).await?;
        Ok(bytes)
    }

    /// Delete a path.
    pub async fn delete(&self, path: &str) -> BackendResult<()> {
        let location = self.full_path(path);
        self.store.delete(&location).await?;
        Ok(())
    }

    /// Check if a path exists.
    pub async fn exists(&self, path: &str) -> BackendResult<bool> {
        let location = self.full_path(path);
        match self.store.head(&location).await {
            Ok(_) => Ok(true),
            Err(object_store::Error::NotFound { .. }) => Ok(false),
            Err(e) => Err(BackendError::ObjectStore(e)),
        }
    }

    /// List paths under a prefix.
    pub async fn list(&self, prefix: &str) -> BackendResult<Vec<String>> {
        use futures::TryStreamExt;
        let location = self.full_path(prefix);
        let mut paths = Vec::new();
        let mut stream = self.store.list(Some(&location));
        while let Some(meta) = stream.try_next().await? {
            paths.push(meta.location.to_string());
        }
        Ok(paths)
    }

    /// Path helpers for bigRAG conventions.
    pub fn wal_path(namespace: &str, seq: u64) -> String {
        format!("wal/{namespace}/{seq:020}.wal")
    }

    pub fn sst_path(namespace: &str, level: u32, seq: u64) -> String {
        format!("index/{namespace}/L{level}/{seq:020}.sst")
    }

    pub fn manifest_path(seq: u64) -> String {
        format!("manifest/{seq:020}.manifest")
    }

    pub fn compacted_path(namespace: &str, seq: u64) -> String {
        format!("compacted/{namespace}/{seq:020}.sst")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_local_backend_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let config = StorageConfig::Local {
            path: dir.path().to_string_lossy().to_string(),
        };
        let backend = StorageBackend::from_config(&config).unwrap();

        // Put and get
        backend
            .put("test/hello.txt", Bytes::from("world"))
            .await
            .unwrap();
        let data = backend.get("test/hello.txt").await.unwrap();
        assert_eq!(data, Bytes::from("world"));

        // Exists
        assert!(backend.exists("test/hello.txt").await.unwrap());
        assert!(!backend.exists("test/missing.txt").await.unwrap());

        // CAS: first put succeeds
        backend
            .put_if_not_exists("test/cas.txt", Bytes::from("first"))
            .await
            .unwrap();

        // CAS: second put fails
        let result = backend
            .put_if_not_exists("test/cas.txt", Bytes::from("second"))
            .await;
        assert!(matches!(result, Err(BackendError::CasConflict(_))));

        // Delete
        backend.delete("test/hello.txt").await.unwrap();
        assert!(!backend.exists("test/hello.txt").await.unwrap());
    }

    #[tokio::test]
    async fn test_list() {
        let dir = tempfile::tempdir().unwrap();
        let config = StorageConfig::Local {
            path: dir.path().to_string_lossy().to_string(),
        };
        let backend = StorageBackend::from_config(&config).unwrap();

        backend
            .put("prefix/a.txt", Bytes::from("a"))
            .await
            .unwrap();
        backend
            .put("prefix/b.txt", Bytes::from("b"))
            .await
            .unwrap();
        backend
            .put("other/c.txt", Bytes::from("c"))
            .await
            .unwrap();

        let paths = backend.list("prefix/").await.unwrap();
        assert_eq!(paths.len(), 2);
    }

    #[test]
    fn test_path_conventions() {
        assert_eq!(
            StorageBackend::wal_path("my-ns", 42),
            "wal/my-ns/00000000000000000042.wal"
        );
        assert_eq!(
            StorageBackend::sst_path("my-ns", 0, 1),
            "index/my-ns/L0/00000000000000000001.sst"
        );
        assert_eq!(
            StorageBackend::manifest_path(100),
            "manifest/00000000000000000100.manifest"
        );
    }
}
