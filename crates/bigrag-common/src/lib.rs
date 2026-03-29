pub mod error;
pub mod types;
pub mod schema;
pub mod config;

/// Shared serde default for `true` — used by config and schema deserializers.
pub(crate) fn default_true() -> bool {
    true
}
