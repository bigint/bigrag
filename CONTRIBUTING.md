# Contributing to bigRAG

Thank you for your interest in contributing to bigRAG. This guide will help you get started.

## Getting Started

### Prerequisites

- **Rust** 1.85+ (edition 2024) — install via [rustup](https://rustup.rs/)
- **Docker** and **Docker Compose** — for integration tests and local development
- **Node.js 22+** — for the UI dashboard (`ui/` directory)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/bigrag-io/bigrag.git
cd bigrag

# Build the project
cargo build

# Run tests
cargo test --workspace

# Run with local storage
cargo run -- --port 8080 --data-dir ./data

# Start dependencies (MinIO) for integration tests
docker compose up -d minio

# Build the UI
cd ui && npm ci && npm run build
```

### Project Structure

```
bigrag/
├── crates/
│   ├── bigrag-api/        # HTTP API layer (Axum routes, handlers)
│   ├── bigrag-common/     # Shared types, errors, utilities
│   ├── bigrag-index/      # Vector (HNSW) and text (BM25) indices
│   ├── bigrag-query/      # Query engine, fusion, filtering
│   └── bigrag-storage/    # Storage backends (local, S3, GCS, Azure)
├── ui/                    # Web dashboard (Next.js)
├── sdks/                  # Client SDKs
├── docs/                  # Documentation
├── Cargo.toml             # Workspace root
├── Dockerfile
├── docker-compose.yml
└── bigrag.example.toml    # Example configuration
```

## Making Changes

### Branching

- Create a feature branch from `main`: `git checkout -b feat/my-feature`
- Use conventional commit prefixes for branch names when helpful: `feat/`, `fix/`, `refactor/`, `docs/`

### Coding Standards

- **Format**: Run `cargo fmt --all` before committing
- **Lint**: Run `cargo clippy --workspace -- -D warnings` and fix all warnings
- **Tests**: Add tests for new functionality. Run `cargo test --workspace` to verify
- **Documentation**: Add doc comments (`///`) for all public types and functions
- **Error handling**: Use `thiserror` for library errors, `anyhow` in binary/test code
- **Unsafe**: Avoid `unsafe` unless absolutely necessary. Document why it is safe if used

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add hybrid search fusion scoring
fix: correct BM25 term frequency calculation
refactor: simplify segment compaction logic
docs: update API reference for query endpoint
test: add integration tests for S3 storage backend
chore: update dependencies
```

### Writing Tests

- **Unit tests**: Place in the same file using `#[cfg(test)]` modules
- **Integration tests**: Place in `tests/` directories within each crate
- **Test naming**: Use descriptive names like `test_hybrid_query_returns_fused_results`

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cosine_similarity_normalized_vectors() {
        // ...
    }

    #[tokio::test]
    async fn test_upsert_and_query_roundtrip() {
        // ...
    }
}
```

## Pull Request Process

1. **Open an issue first** for significant changes to discuss the approach
2. **Create a branch** from `main` with a descriptive name
3. **Make your changes** following the coding standards above
4. **Add tests** covering your changes
5. **Run the full check suite** locally:
   ```bash
   cargo fmt --all -- --check
   cargo clippy --workspace -- -D warnings
   cargo test --workspace
   ```
6. **Push your branch** and open a pull request against `main`
7. **Fill out the PR template** with a clear description of changes
8. **Address review feedback** promptly

### PR Requirements

- All CI checks must pass (fmt, clippy, test, build)
- At least one maintainer approval
- No merge conflicts with `main`
- New public APIs must include documentation

## Reporting Bugs

Open an issue with:

- bigRAG version and how you installed it (Docker, binary, source)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (set `BIGRAG_LOG_LEVEL=debug` for detailed output)

## Feature Requests

Open an issue describing:

- The use case and problem you are trying to solve
- Your proposed solution (if any)
- Any alternatives you have considered

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
