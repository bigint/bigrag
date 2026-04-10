/// Collections resource.
pub mod collections;
/// Documents resource.
pub mod documents;
/// Queries resource.
pub mod queries;
/// Vectors resource.
pub mod vectors;
/// Webhooks resource.
pub mod webhooks;

pub use collections::Collections;
pub use documents::Documents;
pub use queries::Queries;
pub use vectors::Vectors;
pub use webhooks::Webhooks;
