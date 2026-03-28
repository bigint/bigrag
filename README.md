<p align="center">
  <h1 align="center">bigRAG</h1>
  <p align="center">Open-source, self-hostable vector and full-text search database for RAG workloads.</p>
  <p align="center">The open-source answer to turbopuffer.</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/bigrag-io/bigrag/actions/workflows/ci.yml"><img src="https://github.com/bigrag-io/bigrag/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://hub.docker.com/r/bigrag/bigrag"><img src="https://img.shields.io/docker/v/bigrag/bigrag?label=docker" alt="Docker"></a>
</p>

---

## Features

- **Object-storage-first architecture** — S3, GCS, Azure Blob, MinIO, local filesystem
- **Full turbopuffer API compatibility** — drop-in replacement for existing workloads
- **Hybrid search** — ANN + BM25 + metadata filters in a single query
- **Unlimited namespaces** — per-tenant isolation at near-zero cost
- **Docker + Kubernetes native** — `docker run bigrag/bigrag`
- **Sub-10ms warm query latency**
- **Written in Rust** — safe, fast, zero GC pauses
- **Apache 2.0** — run it anywhere, forever free

## Quick Start

### Docker

```bash
docker run -d \
  -p 8080:8080 \
  -v $(pwd)/data:/data \
  bigrag/bigrag:latest
```

### From Source

```bash
cargo build --release
./target/release/bigrag --port 8080 --data-dir ./data
```

### Docker Compose (with MinIO)

```bash
docker compose up -d
```

This starts bigRAG alongside MinIO for S3-compatible object storage. See `docker-compose.yml` for the full configuration.

## Client SDKs

| Language   | Install                                    |
| ---------- | ------------------------------------------ |
| Python     | `pip install bigrag`                       |
| TypeScript | `npm install @bigrag/client`               |
| Go         | `go get github.com/bigrag-io/bigrag-go`    |

## Usage Examples (Python)

### Upsert Vectors

```python
from bigrag import Client

client = Client("http://localhost:8080")

client.upsert(
    namespace="documents",
    vectors=[
        {
            "id": "doc-1",
            "values": [0.1, 0.2, 0.3, ...],  # 768-dim embedding
            "metadata": {"title": "Introduction", "category": "guide"},
            "content": "bigRAG is an open-source vector database..."
        },
        {
            "id": "doc-2",
            "values": [0.4, 0.5, 0.6, ...],
            "metadata": {"title": "Quick Start", "category": "tutorial"},
            "content": "Get started with bigRAG in under 5 minutes..."
        }
    ]
)
```

### ANN Query (Vector Search)

```python
results = client.query(
    namespace="documents",
    vector=[0.1, 0.2, 0.3, ...],
    top_k=10
)

for match in results.matches:
    print(f"{match.id}: {match.score}")
```

### BM25 Query (Full-Text Search)

```python
results = client.query(
    namespace="documents",
    text="how to deploy bigRAG",
    top_k=10,
    search_type="bm25"
)
```

### Hybrid Search (ANN + BM25)

```python
results = client.query(
    namespace="documents",
    vector=[0.1, 0.2, 0.3, ...],
    text="deployment guide",
    top_k=10,
    search_type="hybrid",
    alpha=0.7  # 0.0 = pure BM25, 1.0 = pure ANN
)
```

### Metadata Filters

```python
results = client.query(
    namespace="documents",
    vector=[0.1, 0.2, 0.3, ...],
    top_k=10,
    filters={
        "category": {"$eq": "guide"},
        "date": {"$gte": "2024-01-01"}
    }
)
```

## Usage Examples (TypeScript)

```typescript
import { Client } from "@bigrag/client";

const client = new Client("http://localhost:8080");

// Upsert
await client.upsert("documents", {
  vectors: [
    {
      id: "doc-1",
      values: [0.1, 0.2, 0.3],
      metadata: { title: "Introduction", category: "guide" },
      content: "bigRAG is an open-source vector database...",
    },
  ],
});

// ANN Query
const results = await client.query("documents", {
  vector: [0.1, 0.2, 0.3],
  topK: 10,
});

// Hybrid Search
const hybrid = await client.query("documents", {
  vector: [0.1, 0.2, 0.3],
  text: "deployment guide",
  topK: 10,
  searchType: "hybrid",
  alpha: 0.7,
});

// With Filters
const filtered = await client.query("documents", {
  vector: [0.1, 0.2, 0.3],
  topK: 10,
  filters: {
    category: { $eq: "guide" },
  },
});
```

## Usage Examples (curl)

### Health Check

```bash
curl http://localhost:8080/health
```

### Upsert Vectors

```bash
curl -X POST http://localhost:8080/v1/namespaces/documents/vectors \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": [
      {
        "id": "doc-1",
        "values": [0.1, 0.2, 0.3],
        "metadata": {"title": "Introduction"},
        "content": "bigRAG is an open-source vector database..."
      }
    ]
  }'
```

### Query Vectors

```bash
curl -X POST http://localhost:8080/v1/namespaces/documents/query \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, 0.3],
    "top_k": 10,
    "filters": {
      "title": {"$eq": "Introduction"}
    }
  }'
```

### Delete Vectors

```bash
curl -X DELETE http://localhost:8080/v1/namespaces/documents/vectors \
  -H "Content-Type: application/json" \
  -d '{"ids": ["doc-1", "doc-2"]}'
```

### List Namespaces

```bash
curl http://localhost:8080/v1/namespaces
```

## Configuration

bigRAG is configured via `bigrag.toml` or environment variables. Create a config file:

```toml
[server]
port = 8080
host = "0.0.0.0"
max_connections = 1024

[storage]
backend = "s3"           # "local", "s3", "gcs", "azure"
data_dir = "./data"      # for local backend
bucket = "bigrag-data"   # for object storage backends
prefix = ""

[storage.s3]
region = "us-east-1"
endpoint = ""            # custom endpoint for MinIO
access_key_id = ""
secret_access_key = ""

[index]
default_metric = "cosine"    # "cosine", "euclidean", "dot_product"
max_dimensions = 4096
hnsw_m = 16
hnsw_ef_construction = 200
hnsw_ef_search = 100

[cache]
max_size_mb = 512
ttl_seconds = 300

[compaction]
enabled = true
interval_seconds = 3600
min_segments = 4

[logging]
level = "info"           # "debug", "info", "warn", "error"
format = "json"          # "json", "pretty"
```

### Environment Variables

All configuration options can be set via environment variables with the `BIGRAG_` prefix:

| Variable                      | Description                        | Default       |
| ----------------------------- | ---------------------------------- | ------------- |
| `BIGRAG_PORT`                 | Server listen port                 | `8080`        |
| `BIGRAG_HOST`                 | Server bind address                | `0.0.0.0`     |
| `BIGRAG_STORAGE_BACKEND`      | Storage backend type               | `local`       |
| `BIGRAG_STORAGE_DATA_DIR`     | Local data directory               | `./data`      |
| `BIGRAG_STORAGE_BUCKET`       | Object storage bucket name         | —             |
| `BIGRAG_S3_REGION`            | AWS S3 region                      | `us-east-1`   |
| `BIGRAG_S3_ENDPOINT`          | Custom S3 endpoint (MinIO)         | —             |
| `BIGRAG_CACHE_MAX_SIZE_MB`    | In-memory cache size               | `512`         |
| `BIGRAG_LOG_LEVEL`            | Log level                          | `info`        |

## API Reference

| Method   | Endpoint                                      | Description                       |
| -------- | --------------------------------------------- | --------------------------------- |
| `GET`    | `/health`                                     | Health check                      |
| `GET`    | `/v1/namespaces`                              | List all namespaces               |
| `POST`   | `/v1/namespaces/{ns}/vectors`                 | Upsert vectors                    |
| `POST`   | `/v1/namespaces/{ns}/query`                   | Query vectors (ANN/BM25/hybrid)   |
| `GET`    | `/v1/namespaces/{ns}/vectors/{id}`            | Get vector by ID                  |
| `DELETE` | `/v1/namespaces/{ns}/vectors`                 | Delete vectors by IDs             |
| `DELETE` | `/v1/namespaces/{ns}`                         | Delete a namespace                |
| `GET`    | `/v1/namespaces/{ns}/stats`                   | Namespace statistics              |
| `GET`    | `/metrics`                                    | Prometheus metrics                |

## Architecture

bigRAG uses a 3-tier storage architecture designed for cost efficiency and low latency:

```
                     Queries
                       |
                 +-----v------+
                 |   API Layer |  (Axum, REST + turbopuffer compat)
                 +-----+------+
                       |
              +--------v---------+
              |   Query Engine   |  (ANN + BM25 + filter fusion)
              +--------+---------+
                       |
         +-------------+-------------+
         |             |             |
    +----v----+  +-----v-----+  +---v----+
    |  Hot    |  |   Warm    |  |  Cold  |
    |  Cache  |  |  (Local)  |  | (S3/..)|
    | (Memory)|  |  (mmap)   |  |        |
    +---------+  +-----------+  +--------+
```

- **Hot tier**: In-memory cache (moka) for frequently accessed segments
- **Warm tier**: Memory-mapped local files for recent data
- **Cold tier**: Object storage (S3/GCS/Azure) for long-term, cost-effective storage

Data flows through a write-ahead log, gets indexed into HNSW (vector) and BM25 (text) indices, compacted into immutable segments, and tiered to object storage based on access patterns.

## Deployment

### Docker

```bash
docker run -d \
  --name bigrag \
  -p 8080:8080 \
  -v bigrag-data:/data \
  -e BIGRAG_LOG_LEVEL=info \
  bigrag/bigrag:latest
```

### Docker Compose

See the included `docker-compose.yml` for a full setup with MinIO:

```bash
docker compose up -d
```

### Kubernetes (Helm)

```bash
helm repo add bigrag https://charts.bigrag.io
helm install bigrag bigrag/bigrag \
  --set storage.backend=s3 \
  --set storage.bucket=my-bigrag-bucket
```

### Single Binary

Download the latest release and run directly:

```bash
curl -sSL https://get.bigrag.io | sh
bigrag --port 8080 --data-dir ./data
```

## turbopuffer Compatibility

bigRAG includes a turbopuffer-compatible API layer, making it a drop-in replacement. Point your existing turbopuffer client at bigRAG:

```python
# Just change the base URL
import tpuf

tpuf.api_base = "http://localhost:8080"
ns = tpuf.Namespace("my-namespace")
ns.upsert(ids=[1, 2], vectors=[[0.1, 0.2], [0.3, 0.4]])
```

### Supported turbopuffer Operations

- Namespace create/delete/list
- Vector upsert (with metadata and content)
- Vector query (ANN, filters)
- Vector delete by ID
- Namespace statistics

### Migration from turbopuffer

1. Deploy bigRAG and configure your storage backend
2. Export your data from turbopuffer using their API
3. Point the turbopuffer client at your bigRAG instance
4. Upsert your exported data
5. Update your application's base URL

## Performance

Target latency at p99, measured with 1M vectors of 768 dimensions:

| Operation              | Warm (cached) | Cold (from S3) |
| ---------------------- | ------------- | -------------- |
| ANN query (top-10)     | < 5ms         | < 50ms         |
| BM25 query (top-10)    | < 8ms         | < 60ms         |
| Hybrid query (top-10)  | < 10ms        | < 80ms         |
| Single vector upsert   | < 2ms         | < 2ms          |
| Batch upsert (1000)    | < 50ms        | < 50ms         |
| Namespace creation     | < 1ms         | < 1ms          |

Performance varies based on hardware, dataset size, and storage backend. Object storage latency depends on network proximity.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the PR process.

## License

[Apache License 2.0](LICENSE) — use it anywhere, forever free.
