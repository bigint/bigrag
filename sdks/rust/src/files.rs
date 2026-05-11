use std::path::{Path, PathBuf};

use reqwest::multipart::Part;

use crate::error::RagComputerError;

/// Input for file upload operations.
///
/// Supports multiple sources: file paths, in-memory bytes, and streaming bodies.
#[derive(Debug)]
pub enum FileInput {
    /// Read from a file path on disk.
    Path(PathBuf),
    /// Read from a file path with an explicit filename override.
    PathWithName {
        /// Path to the file.
        path: PathBuf,
        /// Filename to use in the upload.
        name: String,
    },
    /// In-memory bytes with a filename.
    Bytes {
        /// File content.
        data: Vec<u8>,
        /// Filename to use in the upload.
        name: String,
    },
    /// A streaming body with a filename (for large files without loading into memory).
    Stream {
        /// Reqwest body stream.
        body: reqwest::Body,
        /// Filename to use in the upload.
        name: String,
    },
}

impl FileInput {
    /// Get the filename that will be used for the upload.
    pub fn filename(&self) -> &str {
        match self {
            Self::Path(path) => path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("document"),
            Self::PathWithName { name, .. }
            | Self::Bytes { name, .. }
            | Self::Stream { name, .. } => name,
        }
    }

    /// Convert into a `reqwest::multipart::Part` for upload.
    pub(crate) async fn into_multipart_part(self) -> Result<Part, RagComputerError> {
        match self {
            Self::Path(path) => {
                let name = path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("document")
                    .to_string();
                let bytes = tokio::fs::read(&path).await?;
                Ok(Part::bytes(bytes).file_name(name))
            }
            Self::PathWithName { path, name } => {
                let bytes = tokio::fs::read(&path).await?;
                Ok(Part::bytes(bytes).file_name(name))
            }
            Self::Bytes { data, name } => Ok(Part::bytes(data).file_name(name)),
            Self::Stream { body, name } => Ok(Part::stream(body).file_name(name)),
        }
    }
}

impl From<&str> for FileInput {
    fn from(s: &str) -> Self {
        Self::Path(PathBuf::from(s))
    }
}

impl From<String> for FileInput {
    fn from(s: String) -> Self {
        Self::Path(PathBuf::from(s))
    }
}

impl From<PathBuf> for FileInput {
    fn from(p: PathBuf) -> Self {
        Self::Path(p)
    }
}

impl From<&Path> for FileInput {
    fn from(p: &Path) -> Self {
        Self::Path(p.to_path_buf())
    }
}

impl From<(Vec<u8>, &str)> for FileInput {
    fn from((data, name): (Vec<u8>, &str)) -> Self {
        Self::Bytes {
            data,
            name: name.to_string(),
        }
    }
}
