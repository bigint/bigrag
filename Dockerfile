# Stage 1: Builder
FROM rust:1.86-bookworm AS builder

WORKDIR /build

# Cache dependencies
COPY Cargo.toml Cargo.lock ./
COPY crates/bigrag-common/Cargo.toml crates/bigrag-common/Cargo.toml
COPY crates/bigrag-storage/Cargo.toml crates/bigrag-storage/Cargo.toml
COPY crates/bigrag-index/Cargo.toml crates/bigrag-index/Cargo.toml
COPY crates/bigrag-query/Cargo.toml crates/bigrag-query/Cargo.toml
COPY crates/bigrag-api/Cargo.toml crates/bigrag-api/Cargo.toml
COPY crates/bigrag-server/Cargo.toml crates/bigrag-server/Cargo.toml

# Create dummy src files for dependency caching
RUN mkdir -p crates/bigrag-common/src && echo "pub mod error; pub mod types; pub mod schema; pub mod config;" > crates/bigrag-common/src/lib.rs && \
    mkdir -p crates/bigrag-storage/src && echo "" > crates/bigrag-storage/src/lib.rs && \
    mkdir -p crates/bigrag-index/src && echo "" > crates/bigrag-index/src/lib.rs && \
    mkdir -p crates/bigrag-query/src && echo "" > crates/bigrag-query/src/lib.rs && \
    mkdir -p crates/bigrag-api/src && echo "" > crates/bigrag-api/src/lib.rs && \
    mkdir -p crates/bigrag-server/src && echo "fn main() {}" > crates/bigrag-server/src/main.rs

# Build dependencies only (cache layer)
RUN cargo build --release --bin bigrag 2>/dev/null || true

# Copy actual source
COPY crates/ crates/

# Touch to invalidate cached builds
RUN touch crates/bigrag-common/src/lib.rs && \
    touch crates/bigrag-storage/src/lib.rs && \
    touch crates/bigrag-index/src/lib.rs && \
    touch crates/bigrag-query/src/lib.rs && \
    touch crates/bigrag-api/src/lib.rs && \
    touch crates/bigrag-server/src/main.rs

# Build release binary
RUN cargo build --release --bin bigrag

# Stage 2: Runtime
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -r -s /bin/false bigrag

COPY --from=builder /build/target/release/bigrag /usr/local/bin/bigrag

RUN mkdir -p /data && chown bigrag:bigrag /data

USER bigrag

EXPOSE 8080 9090

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["bigrag"]
CMD ["--host", "0.0.0.0", "--port", "8080", "--data-dir", "/data"]
