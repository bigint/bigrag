# bigRAG Product Requirements Document

> **Version:** 1.0.0
> **Date:** 2026-03-28
> **Status:** Approved for implementation
> **License:** Apache 2.0

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Target Users and Personas](#2-target-users-and-personas)
3. [Competitive Landscape and Positioning](#3-competitive-landscape-and-positioning)
4. [Core Architecture Requirements](#4-core-architecture-requirements)
5. [Data Model](#5-data-model)
6. [Storage Engine Requirements](#6-storage-engine-requirements)
7. [Storage Backends](#7-storage-backends)
8. [Indexing System Requirements](#8-indexing-system-requirements)
9. [Query Engine Requirements](#9-query-engine-requirements)
10. [Write Engine Requirements](#10-write-engine-requirements)
11. [Filter Engine Requirements](#11-filter-engine-requirements)
12. [Namespace Management](#12-namespace-management)
13. [Schema System](#13-schema-system)
14. [REST API Specification](#14-rest-api-specification)
15. [API Compatibility with turbopuffer](#15-api-compatibility-with-turbopuffer)
16. [Authentication and Authorization](#16-authentication-and-authorization)
17. [Multi-Tenancy Architecture](#17-multi-tenancy-architecture)
18. [Client SDK Strategy](#18-client-sdk-strategy)
19. [Deployment Models](#19-deployment-models)
20. [Docker Deployment](#20-docker-deployment)
21. [Kubernetes Deployment](#21-kubernetes-deployment)
22. [Self-Hosting Requirements](#22-self-hosting-requirements)
23. [Configuration System](#23-configuration-system)
24. [Observability](#24-observability)
25. [Security Model](#25-security-model)
26. [Backup and Disaster Recovery](#26-backup-and-disaster-recovery)
27. [Migration and Import Tools](#27-migration-and-import-tools)
28. [Plugin and Extensibility System](#28-plugin-and-extensibility-system)
29. [Performance Targets](#29-performance-targets)
30. [Open Source Governance and Community](#30-open-source-governance-and-community)
31. [Enterprise Features](#31-enterprise-features)
32. [Admin Dashboard](#32-admin-dashboard)
33. [Testing Strategy](#33-testing-strategy)
34. [Implementation Roadmap](#34-implementation-roadmap)
35. [Competitor Self-Hosting Analysis](#35-competitor-self-hosting-analysis)
36. [Appendix: turbopuffer Feature Parity Matrix](#36-appendix-turbopuffer-feature-parity-matrix)

---

## 1. Product Vision

### 1.1 Mission Statement

bigRAG is the open-source, self-hostable vector and full-text search database purpose-built for Retrieval-Augmented Generation (RAG) workloads. It is the open-source answer to turbopuffer: a serverless vector store that costs a minimum of $64/month with no self-hosted option and no open-source license.

### 1.2 Core Value Propositions

1. **Zero licensing cost** -- Apache 2.0 license, run it anywhere, on any infrastructure, forever free
2. **Object-storage-first architecture** -- S3, GCS, Azure Blob, MinIO, or local disk as the primary store; compute nodes are stateless and replaceable
3. **Full turbopuffer API compatibility** -- drop-in replacement for existing turbopuffer clients with a compatibility mode that requires only changing the base URL
4. **Hybrid search** -- dense vector (ANN), sparse (BM25), and metadata filters unified in a single query call
5. **Unlimited namespaces** -- one namespace per tenant with near-zero marginal cost, matching turbopuffer's model that serves Cursor (10M namespaces), Notion (1M), and Linear (1.5M)
6. **Docker and Kubernetes native** -- single binary, `docker run bigrag/bigrag`, official Helm chart, HPA-ready
7. **Sub-10ms warm query latency** -- matching turbopuffer's warm-tier performance
8. **Written in Rust** -- safe, fast, memory-efficient, zero GC pauses

### 1.3 What bigRAG Is NOT

- bigRAG is not a general-purpose database; it is optimized for vector + full-text search workloads
- bigRAG does not generate embeddings internally (this is deliberate -- embedding models evolve rapidly and are best handled by the application layer); an optional sidecar embedding server is provided
- bigRAG does not attempt to replace relational databases, document databases, or graph databases

---

## 2. Target Users and Personas

### 2.1 Primary Personas

| Persona | Description | Pain Point Solved |
|---------|-------------|-------------------|
| **SaaS startup engineer** | Building a product with AI/RAG features, per-tenant data isolation needed | Cannot afford $64+/month minimum for turbopuffer; needs per-tenant namespace isolation without per-tenant cost |
| **Enterprise platform engineer** | Operating infrastructure for a large organization with data residency requirements | Needs data residency / BYOC without turbopuffer's $4,096/month Enterprise plan; needs to deploy in private VPC/air-gapped environments |
| **AI/RAG developer** | Building RAG applications locally, prototyping before committing to a cloud service | Wants a local dev database matching production semantics with zero cost during development |
| **Open-source project maintainer** | Building an open-source product that needs vector search | No production-grade open-source vector database offers full hybrid search + object storage backend + unlimited namespaces |
| **Platform/infra team** | Embedding vector search capability into a larger platform or product | Wants to embed a vector search engine with a well-defined API boundary, Apache 2.0 licensed |

### 2.2 Secondary Personas

| Persona | Description | Pain Point Solved |
|---------|-------------|-------------------|
| **ML researcher** | Running experiments with different embedding models and search strategies | Needs exposed HNSW/SPFresh tuning parameters, recall monitoring, and the ability to iterate quickly without cloud vendor lock-in |
| **Hobbyist/student** | Learning about vector databases and RAG systems | Free, easy to install, good documentation, local-first |
| **DevOps engineer** | Responsible for deploying and maintaining database infrastructure | Needs standard observability (Prometheus, Grafana), health checks, Helm charts, and straightforward operational procedures |
| **Compliance officer** | Ensuring data handling meets regulatory requirements | Needs audit logs, encryption at rest, data residency guarantees, and GDPR right-to-erasure support via namespace deletion |

### 2.3 Use Cases

1. **Per-tenant RAG** -- SaaS applications where each customer's documents are isolated in a namespace (conversations, knowledge bases, support tickets)
2. **Hybrid search** -- Combining semantic vector search with keyword BM25 search and metadata filtering in a single API call
3. **Local development** -- Running the same database locally that runs in production, with identical semantics
4. **Multi-modal search** -- Multiple vector columns per document (title embedding, content embedding, image embedding) searched independently or fused
5. **Real-time ingestion** -- Continuous ingestion of documents with immediate queryability
6. **Compliance-sensitive workloads** -- GDPR right-to-erasure via namespace deletion, SOC 2 audit logging, HIPAA with TLS + encryption at rest

---

## 3. Competitive Landscape and Positioning

### 3.1 Feature Comparison Matrix

```
                 Self-Hosted?  Open Source?  Object Storage?  Hybrid Search?  Multi-tenant?
turbopuffer          No            No             Yes               Yes           Yes (unlimited ns)
bigRAG               YES           YES            YES               YES           YES
Qdrant               Yes           Yes            Partial           Partial       Limited
Weaviate             Yes           Yes            No                Yes           Limited
Milvus               Yes           Yes            Yes (Kafka WAL)   Partial       Yes
pgvector             Yes           Yes            No                No            Per-schema
Chroma               Yes           Yes            No                Partial       Namespace
Pinecone             No            No             Yes               Yes           Limited
LanceDB              Yes           Yes            Yes               Partial       N/A (embedded)
```

### 3.2 Where bigRAG Matches turbopuffer

1. Object-storage as primary state (not an afterthought)
2. Unlimited namespaces at near-zero marginal cost
3. Hybrid search in one call (BM25 + ANN + metadata filters)
4. Strong consistency by default
5. Multi-query per request (up to 16 parallel query vectors)
6. SPFresh index algorithm
7. Columnar segment format optimized for object storage
8. Three-tier storage hierarchy (DRAM, NVMe, Object Storage)

### 3.3 Where bigRAG Differentiates

| Feature | turbopuffer | bigRAG |
|---------|------------|--------|
| License | Proprietary SaaS | Apache 2.0 |
| Self-hosted | Not available | First-class Docker/K8s |
| Minimum cost | $64/month | $0 (self-hosted) |
| Open source | SDKs only | Entire engine |
| Local dev | No (pay for API) | `docker run bigrag/bigrag` |
| Storage backends | AWS S3, GCS (managed) | S3, GCS, Azure Blob, MinIO, local FS |
| HNSW tuning | Hidden/auto | Exposed (ef_construction, M, ef_search) |
| Cold start | ~400ms | Target <200ms with prefetch hints |
| Filter-aware ANN | Post-filter only | Pre-filter HNSW (planned v2) |
| Dashboard | PHPMyAdmin-style (roadmap) | Day-1 built-in web UI |
| Prometheus metrics | No | Built-in |
| JWT authentication | No | Built-in |
| API key namespace scoping | No | Per-tenant key isolation |
| Document-level access control | No | Key-filter rules |
| Point-in-time recovery | No | WAL-based |
| Namespace export (Parquet) | Manual | Built-in endpoint |
| Geo-filtering | No | Planned v2 |

---

## 4. Core Architecture Requirements

### 4.1 System Architecture

```
+--------------------------------------------------------------------------+
|                            bigRAG Cluster                                  |
|                                                                            |
|  +--------------------------------------------------------------------+  |
|  |                      API Gateway Layer                              |  |
|  |  HTTP/1.1 + HTTP/2  .  REST JSON  .  Auth (API Key / JWT)          |  |
|  |  Rate limiting  .  Request routing  .  Multi-query dispatch         |  |
|  +----------------------------+---------------------------------------+  |
|                               |                                          |
|  +----------------------------v---------------------------------------+  |
|  |                      Query & Write Router                          |  |
|  |  Namespace resolver  .  Shard router  .  Load balancer             |  |
|  +---------+--------------------------------------------+-----------+    |
|            |                                            |                |
|  +---------v-----------+                 +--------------v-----------+    |
|  |   Query Workers     |                 |     Write Workers        |    |
|  |  (read replicas)    |                 |  (namespace WAL writers) |    |
|  |                     |                 |                          |    |
|  |  ANN search         |                 |  Upsert / Patch / Delete |    |
|  |  BM25 search        |                 |  Conditional writes      |    |
|  |  Hybrid fusion      |                 |  Batch coalescer         |    |
|  |  Filter engine      |                 |  Schema validator        |    |
|  +---------+-----------+                 +-------------+------------+    |
|            |                                           |                 |
|  +---------v-------------------------------------------v-----------+     |
|  |                      Storage Abstraction Layer                  |     |
|  |  +-------------+  +--------------+  +----------------------+   |     |
|  |  | L1: DRAM    |  | L2: NVMe     |  | L3: Object Storage   |   |     |
|  |  | Hot cache   |  | SSD cache    |  | S3/GCS/MinIO/Local   |   |     |
|  |  | <1ms        |  | <10ms        |  | ~100-500ms cold      |   |     |
|  |  +-------------+  +--------------+  +----------------------+   |     |
|  +-----------------------------------------------------------------+     |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  |                    Background Services                              |  |
|  |  Index compactor  .  Cache warming  .  Recall monitor               |  |
|  |  Namespace janitor  .  Stats aggregator  .  Backup scheduler        |  |
|  +--------------------------------------------------------------------+  |
+--------------------------------------------------------------------------+
```

### 4.2 Deployment Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Standalone** | Single binary, all components in one process | Development, small deployments, single-node production up to ~50M vectors |
| **Clustered** | Separate query, write, and compactor nodes | Production horizontal scaling, high-availability |
| **Embedded** | Library mode (Rust crate, `bigrag-core`) | Embedding bigRAG into another Rust application |
| **Serverless** | Deploy on Fly.io, Railway, Render with persistent volume | Zero-ops cloud deployment for small-to-medium workloads |

### 4.3 Key Design Principles

1. **Object storage is the only source of truth.** All durability comes from the object store. Compute nodes are 100% stateless and replaceable. Losing a compute node loses only the in-flight WAL batch (max 1 second of writes).
2. **LSM-tree semantics over object storage.** Writes append new segment files; background compaction merges segments; the WAL directory is the primary log.
3. **Namespace = prefix on object storage.** A namespace named `tenant-abc` maps to prefix `ns/tenant-abc/` in the bucket. No database migration required for new tenants.
4. **Stateless compute enables unlimited scale-out.** Any query node can serve any namespace without pre-routing. Failover is instantaneous.
5. **Minimize object storage round trips.** The primary latency driver for cold reads. bigRAG's index format (bigRAG Segment Format, BSF) is designed to answer ANN queries in 4 or fewer S3 GET requests.
6. **Recall >= 90% at 1,000 QPS.** ANN index must achieve 90%+ recall at real production load, not just synthetic benchmarks.

### 4.4 Current Implementation State

The codebase currently has the following implemented:

**Crate structure (implemented):**
- `bigrag-common` -- config, types, schema, error types
- `bigrag-storage` -- StorageBackend (local/S3/GCS/Azure via `object_store` crate), MemTable (crossbeam skip list), WAL with group commit, SSTable format with LZ4/ZSTD compression, Bloom filters, ManifestManager with CAS-based epoch fencing, BlockCache (moka), CompactionScheduler (L0 tiered)
- `bigrag-index` -- VectorIndex (SPFresh-style centroid-based partitioning with posting lists), InvertedIndex (BM25 with MAXSCORE block optimization)
- `bigrag-query` -- Filter DSL parser/evaluator (And/Or/Not, 23 operators), ranking parser (ANN, kNN, BM25, Sum, Max, Product, Saturate, Decay, Dist, FilterAsRank, OrderByAttribute), query executor
- `bigrag-api` -- Axum HTTP server, routes (v1 and v2 endpoints), handlers (write, query, delete, list namespaces, namespace metadata, health check, cache warm, debug recall), auth middleware (Bearer token), AppState with in-memory namespace document store
- `bigrag-server` -- main binary with CLI (clap), config, tracing, tower-http layers (trace, compression, CORS)

**What is working:**
- Local filesystem storage backend with full read/write
- WAL with group commit (1-second batching)
- SSTable build/read with LZ4/ZSTD compression and CRC32 integrity
- Bloom filter for point lookups
- Manifest-based state management with CAS epoch fencing
- Block cache (moka) for data blocks and metadata
- L0 compaction (WAL SSTs merged into sorted runs)
- In-memory document store per namespace for query serving
- Full filter DSL evaluation (Eq, NotEq, Lt, Lte, Gt, Gte, In, NotIn, Contains, And, Or, Not)
- Vector ANN search (centroid-based posting lists)
- Vector kNN exact search
- BM25 full-text search with MAXSCORE block optimization
- Hybrid ranking (Sum, Max, Product, Saturate, Decay)
- API key authentication (Bearer token)
- Health check endpoint
- turbopuffer-compatible v2 endpoints (write, query, delete)
- Row and column format upserts
- Multi-query support

**What needs to be built (gaps between implementation and spec):**
- S3/GCS/Azure backends are configured but not tested in CI
- NVMe L2 cache tier (only DRAM L1 exists)
- HNSW index (alternative to SPFresh)
- Patch operations (partial document updates)
- Delete by filter, patch by filter
- Conditional writes
- Aggregations (count, sum, min, max, group_by, distinct)
- Cursor-based pagination
- Schema API endpoints (GET/PUT schema)
- Namespace copy, export (Parquet/JSONL)
- API key management endpoints (create, list, revoke, scope)
- JWT authentication
- Prometheus metrics endpoint
- Admin endpoints (compact, warm, config)
- Admin dashboard (Next.js/shadcn)
- Recall monitoring and auto-tuning
- Backup scheduler, point-in-time recovery
- Migration tools
- SDKs (Python, TypeScript, Go, Java, Ruby)
- Helm chart
- Dockerfile
- TLS support
- Document-level access control

---

## 5. Data Model

### 5.1 Hierarchy

```
Organization
  Namespace (unlimited)
    Schema (evolves online)
      Vector columns (1..N)
      Attribute columns (0..256)
      FTS indexes (0..N)
    Documents (0..500M per namespace)
      id (required, unique within namespace)
      vector (optional, must match schema)
      attributes (key-value, typed)
```

### 5.2 Document

A document is the atomic unit of storage and retrieval. Every document:
- Has a unique `id` within its namespace
- May have one or more vector columns
- May have zero or more typed attribute columns
- Is versioned internally (MVCC-lite for conditional writes)

**ID types:**
- `uint64`: 64-bit unsigned integer (most compact)
- `uuid`: 128-bit UUID in standard hyphenated string format
- `string`: UTF-8 string, max 64 bytes

**Vector representation:**
- JSON array of f32 floats: `[0.1, 0.2, ...]`
- Base64-encoded little-endian f32: `"base64:AAAA..."` (bandwidth optimized)
- Base64-encoded little-endian f16: `"base64f16:..."` (50% storage reduction)

### 5.3 Attribute Types

| Type | Description | Filter Operations |
|------|-------------|-------------------|
| `string` | UTF-8 text, max 8 MiB | Eq, NotEq, In, NotIn, Contains, Glob, Regex |
| `int` | Signed 64-bit integer | Eq, NotEq, Lt, Lte, Gt, Gte, In, NotIn |
| `uint` | Unsigned 64-bit integer | Eq, NotEq, Lt, Lte, Gt, Gte, In, NotIn |
| `float` | IEEE 754 f64 | Eq, NotEq, Lt, Lte, Gt, Gte |
| `bool` | Boolean | Eq, NotEq |
| `uuid` | UUID v4/v7 | Eq, NotEq, In, NotIn |
| `datetime` | ISO 8601 UTC | Eq, NotEq, Lt, Lte, Gt, Gte |
| `[]string` | Array of strings | Contains, ContainsAny, ContainsAll, AnyEq, AnyGlob |
| `[]int` | Array of ints | AnyEq, AnyLt, AnyLte, AnyGt, AnyGte, Contains |
| `[]uint` | Array of uints | AnyEq, AnyLt, AnyLte, AnyGt, AnyGte |
| `[]float` | Array of floats | AnyEq, AnyLt, AnyLte, AnyGt, AnyGte |
| `[]bool` | Array of bools | AnyEq, Contains |
| `[]uuid` | Array of UUIDs | Contains, ContainsAny, ContainsAll |
| `[]datetime` | Array of datetimes | AnyLt, AnyGt, AnyLte, AnyGte |

All attributes are nullable. A null value is distinct from the absence of the attribute.

**Filterable vs. Non-filterable:**
- Default: `filterable: true` -- attribute has an index, supports sorting and filtering
- `filterable: false` -- 50% storage discount, attribute is stored as opaque bytes, cannot be filtered/sorted

### 5.4 Namespace

A namespace is an isolated container with its own:
- Schema (vector dimension, distance metric, attribute types)
- ANN index
- BM25 inverted index (per FTS-enabled attribute)
- Attribute indexes (B-tree for range, hash for equality, regex trie for patterns)
- Object storage prefix: `{bucket}/{namespace_id}/`

**Namespace naming:**
- Pattern: `[A-Za-z0-9\-_\.]{1,128}`
- Recommended multi-tenant pattern: `{env}_{table}_{tenant_id}`

---

## 6. Storage Engine Requirements

### 6.1 Three-Tier Storage Hierarchy

```
Tier 1 -- DRAM (L1)
  Size: Configurable (default: 20% of available RAM)
  Latency: <1ms
  Eviction: LRU with frequency counter (LIRS variant)
  Contents: Hot namespace ANN indexes, BM25 posting lists, attribute indexes

Tier 2 -- NVMe SSD (L2)
  Size: Configurable (default: all available NVMe)
  Latency: <10ms
  Eviction: LRU per namespace, with namespace TTL
  Contents: Warm namespace segments (BSF files), decompressed vectors

Tier 3 -- Object Storage (L3)
  Size: Unlimited
  Latency: ~50-500ms (cold read)
  Durability: Provider SLA (99.999999999% for S3)
  Contents: WAL segments, merged segment files (BSF), schema manifests
```

### 6.2 bigRAG Segment Format (BSF)

The binary segment format is optimized for:
- Answering ANN queries in 4 or fewer object storage GET requests
- Columnar layout for efficient metadata filtering
- Integrated compression per column type (LZ4 for speed, ZSTD for density)

**BSF file layout:**
- Header: magic (0x42534601), version, flags, doc count, segment ID (UUIDv7), key range, timestamp
- Column directory: per-column name, type, offset, length, compression codec
- ID column: sorted array for O(log n) binary search
- Vector columns: RaBitQ binary quantized vectors + full-precision residuals + centroid table + cluster assignments
- Attribute columns: B-tree index, bloom filter, dictionary encoding for low-cardinality strings
- BM25 inverted index: vocabulary, posting lists with skip lists (MAXSCORE/WAND acceleration)
- Footer: CRC32C checksum + metadata JSON blob

### 6.3 LSM-Tree Over Object Storage

**Write flow:**
1. Client write request received
2. Batch coalescer (max 1s or 512MB) groups concurrent writes
3. WAL writer appends to `wal/{seq}.wal` on object storage
4. HTTP 200 returned to client (write is durable)
5. Async indexer (background) builds BSF segment at L0
6. Compaction promotes L0 segments to L1, L1 to L2

**Read flow:**
1. Check L1 cache (DRAM) -- HIT: return immediately
2. Check L2 cache (NVMe) -- HIT: return and promote to L1
3. Enumerate manifest (1 GET request)
4. Fetch relevant BSF column sections (1-4 GET requests)
5. Populate L2 and L1 caches
6. Return results

### 6.4 WAL Design

- Each namespace has its own WAL stream, independent of other namespaces
- WAL entries are write-ahead: the client receives HTTP 200 only after durable commit to object storage
- WAL segments are immutable after commitment
- Max 1 WAL entry per second per namespace (concurrent writes within the window are coalesced)
- Max WAL batch size: 512 MB
- WAL segment format: header (magic, namespace, sequence, previous hash, timestamp) + entries (operation type, count, LZ4-compressed payload, CRC32C per entry) + footer (entry count, total bytes, segment CRC32C)

### 6.5 Compaction Strategy

Leveled compaction with size-tiered merging at L0:

| Level | Target Size | Trigger | Merge Strategy |
|-------|-------------|---------|----------------|
| L0 | < 64 MB | Every flush | Size-tiered: merge 4+ L0 segments |
| L1 | 64 MB - 512 MB | L0 to L1 promotion | Sorted merge |
| L2 | 512 MB - 2 GB | L1 to L2 promotion | Full merge with re-indexing |

Compaction is namespace-local. Compacting namespace A never touches namespace B. Tombstones are applied during compaction and deleted vectors are removed from the merged segment.

---

## 7. Storage Backends

### 7.1 Supported Backends

| Backend | Config Name | Use Case | Current Status |
|---------|-------------|----------|----------------|
| **Local filesystem** | `local` | Development, single-node production, testing | Implemented and tested |
| **AWS S3** | `s3` | Production workloads on AWS | Implemented (needs integration testing) |
| **Google Cloud Storage** | `gcs` | Production workloads on GCP | Implemented (needs integration testing) |
| **Azure Blob Storage** | `azure` | Production workloads on Azure | Implemented (needs integration testing) |
| **MinIO** | `minio` (uses `s3` with custom endpoint) | Self-hosted S3-compatible, air-gapped deployments, development | Needs explicit configuration documentation |
| **Ceph (S3-compatible)** | `s3` with custom endpoint | On-premises enterprise | Works via S3 compatibility |
| **DigitalOcean Spaces** | `s3` with custom endpoint | DigitalOcean deployments | Works via S3 compatibility |
| **Backblaze B2** | `s3` with custom endpoint | Budget-friendly cloud storage | Works via S3 compatibility |

### 7.2 Backend Configuration

Each backend is configured via the `StorageConfig` enum:

**Local:**
```toml
[storage]
backend = "local"
path = "/data/bigrag"
```

**S3:**
```toml
[storage]
backend = "s3"
bucket = "my-bigrag-bucket"
region = "us-east-1"
prefix = "bigrag/"
# Credentials via AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
# or IAM role / instance profile
```

**GCS:**
```toml
[storage]
backend = "gcs"
bucket = "my-bigrag-bucket"
prefix = "bigrag/"
# Credentials via GOOGLE_APPLICATION_CREDENTIALS env var
# or GKE Workload Identity
```

**Azure:**
```toml
[storage]
backend = "azure"
container = "bigrag"
account = "mystorageaccount"
prefix = "bigrag/"
# Credentials via AZURE_STORAGE_ACCOUNT_KEY env var
# or Azure Managed Identity
```

**MinIO (S3-compatible):**
```toml
[storage]
backend = "s3"
bucket = "bigrag"
region = "us-east-1"
prefix = ""
endpoint = "http://minio:9000"
# Credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
```

### 7.3 Backend Interface Requirements

All backends must support these operations (implemented in `StorageBackend`):
- `put(path, data)` -- write data, overwrite if exists
- `put_if_not_exists(path, data)` -- CAS write, fail if exists (used for manifest and epoch fencing)
- `get(path)` -- read full object
- `get_range(path, range)` -- read byte range (used for BSF column reads)
- `delete(path)` -- delete object
- `exists(path)` -- head check
- `list(prefix)` -- list objects under prefix

---

## 8. Indexing System Requirements

### 8.1 ANN Vector Index

**Primary algorithm: SPFresh** (Streaming Partition-based Fresh index)
- Graph-free design: avoids HNSW's requirement to traverse thousands of graph nodes
- Centroid-based: partitions vectors into clusters; queries fetch the top-k centroids then refine within clusters
- Incremental updates: new vectors are assigned to existing clusters without full index rebuild
- Low read amplification: 3-4 object store GET requests per query (vs. 20-100+ for HNSW on object storage)
- Currently implemented as `VectorIndex` in `bigrag-index` with centroid table, posting lists, and automatic cluster splitting

**Alternative: HNSW** (for deployments where data is fully NVMe/DRAM resident)
- Higher recall at higher memory cost
- Configurable parameters: `M` (16), `ef_construction` (200), `ef_search` (64)
- Not yet implemented; planned for Phase 2

**Distance metrics:**

| Metric | API Name | Formula | Use Case |
|--------|----------|---------|----------|
| Cosine distance | `cosine_distance` | 1 - (a.b)/(|a||b|) | Normalized embeddings (OpenAI, Cohere) |
| Euclidean squared | `euclidean_squared` | sum((ai-bi)^2) | Unnormalized embeddings |
| Dot product | `dot_product` | -(a.b) | Matryoshka, learned metrics |
| Hamming | `hamming` | popcount(a XOR b) | Binary vectors |

Default: `cosine_distance`

**Vector quantization:**

| Format | Storage | Recall Impact | Use When |
|--------|---------|---------------|----------|
| `f32` | 4 bytes/dim | Baseline (100%) | Max precision, smaller datasets |
| `f16` | 2 bytes/dim | ~99% | 2x storage reduction, recommended default |
| `int8` | 1 byte/dim | ~97% | 4x reduction, large datasets |
| `binary` | 1 bit/dim | ~90% | 32x reduction, ultra-scale |

**Recall monitoring:**
- Endpoint: `GET /v1/namespaces/{ns}/recall`
- Periodically samples production queries, runs exhaustive kNN, computes recall@k
- Automated tuning: if recall drops below threshold (default 90%), automatically increases nprobe and triggers background index rebuild
- Manual override: users can set `recall_target: 0.95` in namespace config

### 8.2 Full-Text Search Index (BM25)

**Scoring formula: BM25+** with MAXSCORE/WAND acceleration

```
BM25(q, d) = sum(IDF(t) * (tf(t,d) * (k1 + 1)) / (tf(t,d) + k1 * (1 - b + b * |d|/avgdl)))
```

Parameters: k1=1.2, b=0.75, k3=8.0 (all configurable per FTS attribute)

**Tokenization pipeline:**
1. Unicode normalization (NFC)
2. Tokenizer selection: `word_v3` (default, Unicode word boundary), `ngram` (CJK), `whitespace`, `pre_tokenized_array`
3. Case folding (configurable, default: lowercase)
4. ASCII folding (configurable, default: off)
5. Stop word removal (configurable, default: off) -- languages: english, french, german, spanish, portuguese, italian, dutch, russian, chinese, japanese, korean
6. Stemming (configurable, default: off) -- Snowball stemmer
7. Max token length filter (default: 39 bytes)

**Inverted index structure (implemented in `InvertedIndex`):**
- Block-based posting lists (target 256, max 512 postings per block)
- Per-block max BM25 score for MAXSCORE optimization
- Document length tracking for BM25 normalization
- Vocabulary stored in BTreeMap (sorted trie in BSF format)

**FTS v2 architecture (planned):**
- Dynamic bit-set encoding for high-frequency terms (>1% document frequency)
- MAXSCORE algorithm: partitions query terms into essential and non-essential
- Per-shard WAND scoring: block-max optimization
- Vectorized scoring (AVX2/NEON): processes 8 posting list entries simultaneously

### 8.3 Attribute Indexes

| Index Type | Attribute Types | Operations |
|-----------|----------------|------------|
| **B-tree** | int, uint, float, datetime | Lt, Lte, Gt, Gte, range scans |
| **Hash index** | string, uuid, bool | Eq, NotEq, In, NotIn |
| **Bloom filter** | All types | Fast NOT EXISTS check |
| **Bitmap index** | bool, low-cardinality string | AND/OR across large sets |
| **Regex trie** | string | Glob, Regex, IGlob patterns |
| **Inverted list** | []string, []uuid | Contains, ContainsAny, ContainsAll |

---

## 9. Query Engine Requirements

### 9.1 Rank-By Modes

All ranking modes are implemented in the `ranking.rs` parser and `executor.rs` scorer:

| Mode | Syntax | Description |
|------|--------|-------------|
| ANN vector search | `["vector", "ANN", [...]]` | Approximate nearest neighbor via SPFresh/HNSW |
| kNN exact search | `["vector", "kNN", [...]]` | Exhaustive scan (requires filter in production) |
| BM25 full-text | `["field", "BM25", "query"]` | Full-text search via inverted index |
| Attribute ordering | `["attr", "asc"/"desc"]` | Order by attribute value |
| Sum | `["Sum", [clause1, clause2]]` | Sum of sub-clause scores |
| Max | `["Max", [clause1, clause2]]` | Max of sub-clause scores |
| Product | `["Product", weight, clause]` | Weighted score |
| Saturate | `["Saturate", clause, {midpoint, exponent}]` | Maps score to [0, 1) |
| Decay | `["Decay", clause, {midpoint, exponent}]` | Inverse of saturate |
| Dist | `["Dist", clause, origin]` | Distance between attribute and origin |
| FilterAsRank | (filter expression) | Score 1 if filter matches, else 0 |

### 9.2 Hybrid Search (Multi-Query)

Up to 16 rank_by expressions in a single API call, executed in parallel and fused.

**Fusion methods:**

| Method | Formula | Use Case |
|--------|---------|----------|
| `rrf` | score = sum(1/(k + rank_i)) | Default; robust, no calibration needed |
| `linear` | score = w1*score1 + w2*score2 | Calibrated weights |
| `dbsf` | Distribution-based score fusion | Normalized scores from different systems |

### 9.3 Pagination

- `limit.total`: Maximum total results (max 10,000)
- `limit.per`: Constrain results to at most N per unique value of an attribute (faceted top-k)
- Cursor-based pagination for browsing beyond `limit.total`

### 9.4 Aggregations (Planned)

- `count` -- total matching documents
- `sum` -- sum of numeric attribute
- `min` / `max` -- min/max of attribute
- `group_by` -- group results by attribute value
- `distinct` -- distinct values of attribute

### 9.5 Include/Exclude Attributes

- `include_attributes: true` -- include all attributes
- `include_attributes: ["title", "score"]` -- include only named attributes
- `exclude_attributes: ["content"]` -- exclude named attributes
- `include_vectors: true/false` -- include/exclude vector data in response

---

## 10. Write Engine Requirements

### 10.1 Upsert

Both row and column format supported. Currently implemented in `handlers.rs`:

**Row format:**
```json
{
  "upsert_rows": [
    {"id": "doc-1", "vector": [0.1, 0.2], "title": "Hello"}
  ]
}
```

**Column format:**
```json
{
  "upsert_columns": {
    "id": ["doc-1", "doc-2"],
    "vector": [[0.1, 0.2], [0.3, 0.4]],
    "title": ["Hello", "World"]
  }
}
```

### 10.2 Patch (Planned)

Partial update: only specified attributes are updated, unspecified are preserved, vectors unchanged unless included.

```json
{
  "patch_rows": [
    {"id": "doc-1", "score": 4.8}
  ]
}
```

### 10.3 Delete

**Delete by ID (implemented):**
```json
{"deletes": ["doc-1", "doc-2"]}
```

**Delete by filter (planned):**
```json
{
  "delete_by_filter": {
    "filter": ["category", "Eq", "deprecated"],
    "max_affected": 5000000,
    "allow_partial": false
  }
}
```

### 10.4 Conditional Writes (Planned)

Uses the filter DSL plus `$ref_new` reference for optimistic locking and insert-if-not-exists patterns.

### 10.5 Rate Limits and Backpressure

- Per-namespace write rate: 1 WAL commit/second (concurrent writes coalesced)
- Max batch size: 512 MB per request
- Backpressure: HTTP 429 with `Retry-After` when unindexed data exceeds 2 GB
- Disable backpressure: `X-BigRAG-Disable-Backpressure: true` header for bulk imports

---

## 11. Filter Engine Requirements

### 11.1 Filter DSL

Filters use a JSON array notation. Currently implemented in `filter.rs` with 23 operators:

**Scalar operators:** Eq, NotEq, Lt, Lte, Gt, Gte, In, NotIn, Contains, NotContains, ContainsAny, NotContainsAny, Glob, NotGlob, IGlob, NotIGlob, Regex, ContainsAllTokens, ContainsAnyToken, ContainsTokenSequence

**Array operators:** AnyLt, AnyLte, AnyGt, AnyGte (plus Contains/ContainsAny/ContainsAll from above)

**Boolean combinators:** And, Or, Not

### 11.2 Filter Execution Strategy

1. **Filter-first (pre-filter ANN):** For highly selective filters (<1% hit rate), build candidate set via attribute indexes first, then run ANN within that set
2. **ANN-first then filter (post-filter):** For low-selectivity filters, run ANN to get top-N oversampled candidates, then apply filters
3. **Hybrid (filter + ANN interleaved):** For medium-selectivity filters

### 11.3 Null Handling

- `["field", "Eq", null]` matches documents where field is explicitly null OR absent
- `["field", "NotEq", null]` matches documents where field is present and not null

---

## 12. Namespace Management

### 12.1 CRUD Operations

| Operation | Endpoint | Status |
|-----------|----------|--------|
| List namespaces | `GET /v1/namespaces` | Implemented |
| Get namespace metadata | `GET /v1/namespaces/{ns}/metadata` | Implemented |
| Delete namespace | `DELETE /v2/namespaces/{ns}` | Implemented |
| Copy namespace | `POST /v1/namespaces/{dest}/copy` | Planned |
| Export namespace | `POST /v1/namespaces/{ns}/export` | Planned |
| Get/Update schema | `GET/PUT /v1/namespaces/{ns}/schema` | Planned |

### 12.2 Namespace Lifecycle

```
Created (implicit on first write)
  Active (accepting reads + writes)
    Idle (no traffic for inactivity_timeout)
      Cache evicted from DRAM/NVMe (data safe on object storage)
    Deleted (DELETE endpoint)
      Data removed from object storage after retention_period
```

### 12.3 Namespace Limits (Defaults, All Configurable)

| Limit | Default | Max |
|-------|---------|-----|
| Documents per namespace | 500M | Unlimited (with sharding) |
| Vector dimensions | 10,752 | 65,536 |
| Attributes per namespace | 256 | 1024 |
| Attribute name length | 128 bytes | 512 bytes |
| Document size | 64 MiB | 256 MiB |
| ID size | 64 bytes | 256 bytes |
| Query result limit | 10,000 | 100,000 |

---

## 13. Schema System

### 13.1 Schema Definition

Schemas are defined inline during first write (implicit inference) or explicitly via the schema API.

**Supported schema entry formats:**
- Simple type string: `"string"`, `"int"`, `"[1536]f32"`
- Full config object: `{"type": "string", "filterable": true, "full_text_search": {...}}`

**FTS schema configuration:**
```json
{
  "type": "string",
  "full_text_search": {
    "tokenizer": "word_v3",
    "language": "english",
    "stemming": true,
    "remove_stopwords": false,
    "ascii_folding": true,
    "case_sensitive": false,
    "max_token_length": 39,
    "k1": 1.2,
    "b": 0.75,
    "k3": 8.0
  }
}
```

### 13.2 Online Schema Updates

Safe to apply online:
- Adding `filterable: true` to non-filterable attribute (background index build)
- Adding `full_text_search: true` (background FTS build)
- Changing FTS parameters (background rebuild)
- Removing `filterable` from filterable attribute (immediate index drop)
- Adding new attribute (immediate)

NOT supported online:
- Changing vector dimension
- Changing distance metric
- Changing attribute type
- Removing an attribute (stop writing it; data remains queryable)

### 13.3 Multiple Vector Columns

Multiple vector columns per document, each with independent dimensionality, distance metric, and ANN index. Queried independently or fused via hybrid search.

---

## 14. REST API Specification

### 14.1 Base URL and Versioning

```
{host}/v1/    -- Current stable API
{host}/v2/    -- turbopuffer-compatible API endpoints
```

### 14.2 Endpoint Reference

**Namespaces:**

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/v1/namespaces` | List namespaces (paginated) | Implemented |
| GET | `/v1/namespaces/{ns}/metadata` | Get namespace metadata | Implemented |
| DELETE | `/v2/namespaces/{ns}` | Delete namespace | Implemented |
| POST | `/v1/namespaces/{ns}/copy` | Copy namespace | Planned |
| GET | `/v1/namespaces/{ns}/_debug/recall` | Check ANN recall | Implemented (stub) |
| GET | `/v1/namespaces/{ns}/hint_cache_warm` | Pre-warm cache | Implemented (stub) |
| GET | `/v1/namespaces/{ns}/schema` | Get schema | Planned |
| PUT | `/v1/namespaces/{ns}/schema` | Update schema | Planned |
| GET | `/v1/namespaces/{ns}/stats` | Get detailed stats | Planned |

**Documents:**

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/v2/namespaces/{ns}` | Upsert/delete documents | Implemented |
| POST | `/v2/namespaces/{ns}/query` | Query documents | Implemented |
| GET | `/v1/namespaces/{ns}/documents/{id}` | Get single document | Planned |

**Administration:**

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/health` | Health check | Implemented |
| GET | `/v1/health/ready` | Kubernetes readiness probe | Planned |
| GET | `/v1/health/live` | Kubernetes liveness probe | Planned |
| GET | `/v1/metrics` | Prometheus metrics | Planned |
| POST | `/v1/admin/compact/{ns}` | Trigger manual compaction | Planned |
| POST | `/v1/admin/warm/{ns}` | Pre-warm namespace | Planned |
| GET | `/v1/admin/config` | Get runtime config | Planned |
| POST | `/v1/admin/api-keys` | Create API key | Planned |
| GET | `/v1/admin/api-keys` | List API keys | Planned |
| DELETE | `/v1/admin/api-keys/{id}` | Revoke API key | Planned |

### 14.3 Error Format

```json
{
  "error": {
    "code": "NAMESPACE_NOT_FOUND",
    "message": "Namespace 'tenant-xyz' does not exist",
    "details": {"namespace": "tenant-xyz"},
    "request_id": "req_01ABC123"
  }
}
```

**Error codes:** INVALID_REQUEST (400), SCHEMA_MISMATCH (400), INVALID_FILTER (400), DIMENSION_MISMATCH (400), UNAUTHORIZED (401), FORBIDDEN (403), NAMESPACE_NOT_FOUND (404), DOCUMENT_NOT_FOUND (404), SCHEMA_CONFLICT (409), UNPROCESSABLE (422), RATE_LIMITED (429), INDEX_BUILDING (202), INTERNAL_ERROR (500), SERVICE_UNAVAILABLE (503)

### 14.4 Request/Response Headers

**Request:**
- `Authorization: Bearer {api_key}`
- `Content-Type: application/json`
- `X-BigRAG-Disable-Backpressure: true`
- `X-BigRAG-Consistency: strong|eventual`
- `X-Request-ID: {client_id}`

**Response:**
- `X-Request-ID` (echoed or server-generated)
- `X-BigRAG-Version`
- `X-BigRAG-Region`
- `Retry-After` (on 429)

---

## 15. API Compatibility with turbopuffer

### 15.1 Compatibility Mode

bigRAG accepts turbopuffer's exact API format at `/v2/` endpoints when compatibility mode is enabled:

```toml
[compat]
turbopuffer = true
```

This allows switching turbopuffer clients to bigRAG by only changing the base URL:

```python
# Before (turbopuffer):
import turbopuffer as tpuf
tpuf.api_key = "tpuf_..."
ns = tpuf.Namespace("my-ns")

# After (bigRAG, zero code change):
import turbopuffer as tpuf
tpuf.api_key = "br_..."
tpuf.api_base = "http://localhost:8080/v2"
ns = tpuf.Namespace("my-ns")
```

### 15.2 v2 API Endpoints (turbopuffer-Compatible)

Currently implemented:
- `POST /v2/namespaces/{ns}` -- upsert/delete documents (matches turbopuffer's write endpoint)
- `POST /v2/namespaces/{ns}/query` -- query documents
- `DELETE /v2/namespaces/{ns}` -- delete namespace

### 15.3 Compatibility Test Suite

A dedicated compatibility test suite validates behavior parity:
```bash
bigrag-compat-test --backend turbopuffer  # run against real turbopuffer
bigrag-compat-test --backend bigrag       # run against bigRAG
bigrag-compat-test --diff                 # diff the outputs
```

---

## 16. Authentication and Authorization

### 16.1 API Key Model (Partially Implemented)

Current implementation: simple Bearer token validation against a list of allowed keys (comma-separated via `BIGRAG_API_KEYS` env var or `--api-keys` CLI flag). If no keys are configured, authentication is disabled.

**Target implementation:**

```json
{
  "id": "key_01ABC123",
  "name": "Production Write Key",
  "prefix": "br_",
  "permissions": {
    "namespaces": ["tenant-*"],
    "operations": ["read", "write", "delete"],
    "admin": false
  },
  "expiry": null
}
```

**Permission scopes:** read, write, delete, schema, admin

**Namespace restrictions:** `["*"]` (all), `["tenant-abc"]` (specific), `["tenant-*"]` (glob pattern)

### 16.2 JWT Authentication (Planned)

```toml
[auth.jwt]
enabled = true
issuer = "https://auth.example.com"
audience = "bigrag"
jwks_uri = "https://auth.example.com/.well-known/jwks.json"
namespace_claim = "bigrag_namespaces"
```

### 16.3 Document-Level Access Control (Planned)

Automatic filter injection per API key:
```json
{
  "access_control": {
    "filter": ["owner_id", "Eq", "{api_key.metadata.user_id}"]
  }
}
```

---

## 17. Multi-Tenancy Architecture

### 17.1 Tenant Isolation Models

**Shared namespace cluster (default):** All tenants share compute and NVMe cache. Data is logically isolated by namespace prefix on object storage.

**Dedicated namespace cache:** High-value tenants can have namespaces pinned in NVMe/DRAM:
```json
{"cache": {"pin": true, "tier": "nvme"}}
```

**Separate bigRAG instance:** For complete isolation, deploy a separate bigRAG instance per tenant. Recommended for enterprise tenants with compliance requirements.

### 17.2 Multi-Tenant Naming Convention

```
Pattern: {env}_{table}_{tenant_id}

Examples:
  prod_conversations_user-123
  prod_documents_org-abc
  staging_emails_user-456
```

Benefits:
- List all namespaces for a tenant: `prefix=prod_conversations_user-123`
- List all conversation namespaces: `prefix=prod_conversations_`
- GDPR compliance delete: find all namespaces matching `*_user-123`, delete them

---

## 18. Client SDK Strategy

### 18.1 SDK Priority Order

| Priority | Language | Package | Target Release |
|----------|----------|---------|---------------|
| P0 | Python | `pip install bigrag` | Phase 0 (v0.1 with basic upsert/query) |
| P0 | TypeScript/Node | `npm install @bigrag/client` | Phase 1 |
| P1 | Go | `go get github.com/bigrag-io/bigrag-go` | Phase 1 |
| P1 | Rust | `cargo add bigrag` | Phase 1 (reference implementation) |
| P2 | Java/Kotlin | `io.bigrag:bigrag-java` | Phase 2 |
| P2 | Ruby | `gem install bigrag` | Phase 2 |

### 18.2 SDK Requirements

All SDKs must support:
- Sync and async clients
- Connection pooling with configurable max connections
- Automatic retries with exponential backoff
- Timeout configuration (connect, read, write)
- Bearer token authentication
- Upsert (row and column format)
- Query (all rank_by modes, filters, include/exclude attributes)
- Delete (by ID and by filter)
- Namespace management (list, delete, get metadata)
- Batch operations
- Streaming responses for large result sets
- Type-safe request/response models

### 18.3 Framework Integrations

- **LangChain** -- `BigRAGVectorStore` adapter with hybrid search support
- **LlamaIndex** -- `BigRAGVectorStore` for `VectorStoreIndex`
- **OpenAI-compatible embedding sidecar** -- optional Docker sidecar that runs embedding models locally (Nomic, BGE, E5 via Candle/ONNX) with `/v1/embeddings` endpoint

---

## 19. Deployment Models

### 19.1 Deployment Matrix

| Deployment | Target Users | Prerequisites | Complexity |
|-----------|-------------|---------------|------------|
| `docker run` | Developers, hobbyists | Docker | Minimal |
| Docker Compose | Small teams, dev environments | Docker, Docker Compose | Low |
| Docker Compose + MinIO | Self-hosted S3-compatible | Docker, Docker Compose | Low |
| Docker Compose + S3 | Production (single node) | Docker, AWS credentials | Medium |
| Kubernetes (Helm) | Production, multi-node | K8s cluster, Helm, S3/GCS/Azure | Medium-High |
| Single binary | Edge, embedded, serverless | None (static binary) | Minimal |
| Embedded (Rust crate) | Library integration | Rust toolchain | N/A |

### 19.2 Infrastructure Requirements by Scale

| Scale | Vectors | Compute | Memory | Storage | Object Store |
|-------|---------|---------|--------|---------|-------------|
| Tiny | <100K | 1 CPU | 512 MB | 1 GB local | Optional |
| Small | 100K-1M | 2 CPU | 2 GB | 10 GB local/NVMe | Recommended |
| Medium | 1M-50M | 4 CPU | 16 GB | 100 GB NVMe | Required (S3/GCS) |
| Large | 50M-500M | 8 CPU | 32 GB | 500 GB NVMe | Required |
| XLarge | 500M-5B | 16+ CPU (multi-node) | 64+ GB | 1+ TB NVMe | Required |

---

## 20. Docker Deployment

### 20.1 Quick Start

```bash
docker run -d \
  --name bigrag \
  -p 8080:8080 \
  -v $(pwd)/data:/data \
  -e BIGRAG_STORAGE_BACKEND=local \
  -e BIGRAG_STORAGE_PATH=/data \
  -e BIGRAG_AUTH_MASTER_KEY=br_dev_key \
  bigrag/bigrag:latest
```

### 20.2 Docker Compose -- Development

```yaml
version: "3.9"
services:
  bigrag:
    image: bigrag/bigrag:latest
    container_name: bigrag
    restart: unless-stopped
    ports:
      - "8080:8080"
      - "9090:9090"
    volumes:
      - bigrag_data:/data
      - ./bigrag.toml:/etc/bigrag/config.toml:ro
    environment:
      BIGRAG_CONFIG: /etc/bigrag/config.toml
      BIGRAG_LOG_LEVEL: info
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  minio:
    image: minio/minio:latest
    container_name: bigrag-minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data

  bigrag-ui:
    image: bigrag/ui:latest
    ports:
      - "3000:3000"
    environment:
      BIGRAG_URL: http://bigrag:8080
      BIGRAG_API_KEY: br_dev_key

volumes:
  bigrag_data:
  minio_data:
```

### 20.3 Docker Compose -- Production with S3

```yaml
services:
  bigrag:
    image: bigrag/bigrag:latest
    environment:
      BIGRAG_STORAGE_BACKEND: s3
      BIGRAG_STORAGE_BUCKET: my-bigrag-bucket
      BIGRAG_STORAGE_REGION: us-east-1
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      BIGRAG_AUTH_MASTER_KEY: ${BIGRAG_AUTH_MASTER_KEY}
      BIGRAG_CACHE_NVME_PATH: /nvme
      BIGRAG_CACHE_NVME_SIZE_GB: 100
    volumes:
      - /nvme/bigrag:/nvme
    ports:
      - "8080:8080"
```

### 20.4 Dockerfile Requirements

- Multi-stage build: Rust builder stage + minimal runtime stage (distroless or alpine)
- Statically linked binary (musl target for zero runtime dependencies)
- Non-root user
- Health check instruction
- Labels for OCI metadata
- Support for linux/amd64 and linux/arm64

### 20.5 Single Binary Mode

```bash
curl -L https://github.com/bigrag-io/bigrag/releases/latest/download/bigrag-linux-amd64 -o bigrag
chmod +x bigrag
./bigrag server \
  --storage-backend s3 \
  --storage-bucket my-bucket \
  --auth-key br_my_key \
  --port 8080
```

---

## 21. Kubernetes Deployment

### 21.1 Architecture on Kubernetes

**Standalone mode (single deployment):**
- Simple Deployment with 1+ replicas
- All query, write, and compaction in one process
- HPA on CPU utilization
- PersistentVolume for NVMe cache (optional)

**Clustered mode (separate components):**
- `bigrag-query` Deployment: HPA 2-20 replicas, 4 CPU / 16Gi RAM, anti-affinity across zones
- `bigrag-write` Deployment: HPA 2-10 replicas, 2 CPU / 8Gi RAM
- `bigrag-compactor` StatefulSet: 1-3 replicas with distributed lock, 4 CPU / 8Gi RAM

### 21.2 Helm Chart

```bash
helm repo add bigrag https://charts.bigrag.io
helm install bigrag bigrag/bigrag \
  --set storage.backend=s3 \
  --set storage.bucket=my-bucket \
  --set storage.region=us-east-1 \
  --set auth.masterKey=br_production_key \
  --set query.replicas=3 \
  --set query.resources.memory=16Gi \
  --set cache.nvme.enabled=true \
  --set cache.nvme.size=500Gi
```

### 21.3 Helm Values Reference

```yaml
image:
  repository: bigrag/bigrag
  tag: latest
  pullPolicy: IfNotPresent

storage:
  backend: s3
  bucket: bigrag
  region: us-east-1
  prefix: bigrag/
  endpoint: ""
  credentials:
    existingSecret: aws-credentials

auth:
  masterKey: ""
  existingSecret: bigrag-auth
  jwtEnabled: false

query:
  replicas: 3
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
  resources:
    requests: {cpu: 2, memory: 8Gi}
    limits: {cpu: 4, memory: 16Gi}

write:
  replicas: 2
  resources:
    requests: {cpu: 1, memory: 4Gi}

compactor:
  replicas: 2
  resources:
    requests: {cpu: 2, memory: 4Gi}

cache:
  dram:
    size: "20%"
  nvme:
    enabled: false
    storageClass: "fast-nvme"
    size: 500Gi

metrics:
  enabled: true
  serviceMonitor: true

dashboard:
  enabled: true
  ingress:
    enabled: true
    host: bigrag.example.com
    tls: true

tls:
  enabled: false
  secretName: bigrag-tls

ingress:
  enabled: true
  className: nginx
  host: api.bigrag.example.com
  tls: true
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: 512m
```

### 21.4 Kubernetes Resources Generated

- Deployment (query, write) or StatefulSet (compactor)
- Service (ClusterIP for internal, LoadBalancer/Ingress for external)
- ConfigMap (bigrag.toml)
- Secret (API keys, cloud credentials)
- ServiceMonitor (for Prometheus Operator)
- HorizontalPodAutoscaler
- PodDisruptionBudget
- NetworkPolicy (optional)
- Ingress / IngressRoute

---

## 22. Self-Hosting Requirements

### 22.1 Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 1 core | 4 cores |
| RAM | 512 MB | 8 GB |
| Disk | 1 GB | 100 GB NVMe SSD |
| Network | 10 Mbps | 1 Gbps |
| OS | Linux (glibc 2.31+) or Docker | Linux with NVMe |
| Object store | Local FS (dev) | S3/GCS/MinIO |

### 22.2 Supported Platforms

- **Linux:** x86_64, aarch64 (native binary or Docker)
- **macOS:** x86_64, aarch64 (Apple Silicon) -- for development
- **Windows:** via WSL2 or Docker Desktop -- for development
- **Docker:** Official images for linux/amd64, linux/arm64
- **Kubernetes:** Any conformant K8s 1.25+

### 22.3 Cloud Provider Support

| Provider | Object Store | Instance Type Recommendation | Region Support |
|----------|-------------|------------------------------|----------------|
| AWS | S3 | i3/i4i (NVMe), c6g (ARM) | All regions |
| GCP | GCS | n2d (NVMe local SSD) | All regions |
| Azure | Azure Blob | Lsv2 (NVMe local) | All regions |
| DigitalOcean | Spaces (S3-compat) | Premium CPU | All regions |
| Hetzner | MinIO on local disk | Dedicated servers | EU/US |
| On-premises | MinIO/Ceph | Any x86_64/ARM server | N/A |

---

## 23. Configuration System

### 23.1 Configuration Sources (Priority Order)

1. **CLI flags** (highest priority): `--port 8080`
2. **Environment variables**: `BIGRAG_PORT=8080`
3. **Config file (TOML)**: `bigrag.toml` loaded via `--config` flag
4. **Defaults** (lowest priority)

Configuration is managed by `figment` with TOML and env support (already in dependencies).

### 23.2 bigrag.toml Full Reference

```toml
[server]
host = "0.0.0.0"
port = 8080
metrics_port = 9090
max_connections = 10000
request_timeout_ms = 60000
max_request_body_mb = 512

[storage]
backend = "s3"           # s3 | gcs | azureblob | minio | local
bucket = "bigrag-prod"
region = "us-east-1"
prefix = "bigrag/"
endpoint = ""            # custom endpoint for MinIO/Ceph

[cache]
dram_max_bytes = 0       # 0 = 20% of available RAM
dram_eviction = "lru"    # lru | lfu | arc
nvme_path = "/var/cache/bigrag"
nvme_max_bytes = 0       # 0 = use all available disk
nvme_eviction = "lru"
namespace_inactivity_evict_secs = 3600
hot_namespace_pin = []

[indexing]
ann_algorithm = "spfresh"   # spfresh | hnsw
ann_default_recall_target = 0.90
ann_nprobe_factor = 1.0
hnsw_m = 16
hnsw_ef_construction = 200
hnsw_ef_search = 64
default_vector_type = "f32" # f32 | f16 | int8 | binary
fts_ram_budget_mb = 1024
l0_merge_threshold = 4
l1_max_segment_mb = 512
l2_max_segment_mb = 2048
compaction_workers = 2

[auth]
master_key = ""
disable = false

[auth.jwt]
enabled = false
issuer = ""
audience = ""
jwks_uri = ""

[limits]
max_vector_dimensions = 10752
max_document_size_mb = 64
max_batch_size_mb = 512
max_attributes_per_namespace = 256
max_concurrent_queries = 64
max_query_result = 10000
max_aggregation_groups = 10000
max_delete_by_filter = 5000000
max_patch_by_filter = 50000
write_backpressure_threshold_gb = 2

[observability]
log_level = "info"
log_format = "json"      # json | text
slow_query_threshold_ms = 100
enable_query_log = false
metrics_prefix = "bigrag"

[tls]
enabled = false
cert_file = ""
key_file = ""
ca_file = ""             # for mTLS

[backup]
enabled = false
schedule = "0 2 * * *"
retain_days = 7
destination_bucket = ""
namespace_filter = "*"

[compat]
turbopuffer = true
```

### 23.3 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_STORAGE_BACKEND` | `s3`, `gcs`, `azureblob`, `minio`, `local` | `local` |
| `BIGRAG_STORAGE_BUCKET` | Bucket name (or path for local) | `bigrag-data` |
| `BIGRAG_STORAGE_REGION` | Cloud region | `us-east-1` |
| `BIGRAG_STORAGE_ENDPOINT` | Custom endpoint (MinIO, Ceph) | -- |
| `BIGRAG_STORAGE_PREFIX` | Object key prefix | `bigrag/` |
| `BIGRAG_CACHE_DRAM_SIZE` | L1 DRAM cache size | `20%` of RAM |
| `BIGRAG_CACHE_NVME_PATH` | L2 NVMe cache directory | `/tmp/bigrag-nvme` |
| `BIGRAG_CACHE_NVME_SIZE` | L2 NVMe cache max size | `all available` |
| `BIGRAG_AUTH_MASTER_KEY` | Master API key | -- |
| `BIGRAG_AUTH_DISABLE` | Disable auth (dev only) | `false` |
| `BIGRAG_API_KEYS` | Comma-separated API keys | -- |
| `BIGRAG_LOG_LEVEL` | `debug`, `info`, `warn`, `error` | `info` |
| `BIGRAG_LOG_FORMAT` | `json`, `text` | `json` |
| `BIGRAG_PORT` | HTTP server port | `8080` |
| `BIGRAG_METRICS_PORT` | Prometheus metrics port | `9090` |
| `BIGRAG_MAX_NAMESPACES` | Max namespaces (0 = unlimited) | `0` |
| `BIGRAG_COMPACTION_WORKERS` | Background compaction threads | `2` |
| `BIGRAG_WRITE_WORKERS` | WAL writer threads | `4` |
| `BIGRAG_QUERY_WORKERS` | Query handler threads | `num_cpus` |
| `BIGRAG_TLS_CERT` | Path to TLS certificate | -- |
| `BIGRAG_TLS_KEY` | Path to TLS private key | -- |
| `AWS_ACCESS_KEY_ID` | AWS credentials | -- |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | -- |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCS credentials file path | -- |
| `AZURE_STORAGE_ACCOUNT_KEY` | Azure credentials | -- |

---

## 24. Observability

### 24.1 Health Checks

**General health:**
```
GET /health
{"status": "ok", "version": "0.1.0"}
```

**Kubernetes readiness probe (planned):**
```
GET /v1/health/ready
```
Returns 200 when the server can accept traffic (storage backend reachable, at least one namespace loadable).

**Kubernetes liveness probe (planned):**
```
GET /v1/health/live
```
Returns 200 when the server process is alive and not deadlocked.

### 24.2 Prometheus Metrics (Planned)

Core metrics (exposed at `GET /v1/metrics`):

| Metric | Type | Description |
|--------|------|-------------|
| `bigrag_queries_total` | Counter | Total queries (labels: namespace, status, type) |
| `bigrag_query_duration_ms` | Histogram | Query latency histogram |
| `bigrag_writes_total` | Counter | Total write operations |
| `bigrag_write_duration_ms` | Histogram | Write latency histogram |
| `bigrag_documents_total` | Gauge | Total documents per namespace |
| `bigrag_storage_bytes` | Gauge | Storage used per namespace |
| `bigrag_cache_hits_total` | Counter | Cache hits by tier (dram/nvme/cold) |
| `bigrag_cache_misses_total` | Counter | Cache misses by tier |
| `bigrag_cache_hit_ratio` | Gauge | Cache hit ratio |
| `bigrag_ann_recall` | Gauge | Estimated ANN recall per namespace |
| `bigrag_fts_queries_total` | Counter | BM25 query count |
| `bigrag_compaction_runs_total` | Counter | Compaction job count |
| `bigrag_compaction_duration_ms` | Histogram | Compaction duration |
| `bigrag_index_build_duration_ms` | Histogram | Index build latency |
| `bigrag_wal_segments_total` | Gauge | Uncompacted WAL segments per namespace |
| `bigrag_object_store_requests_total` | Counter | Object store requests by operation |
| `bigrag_object_store_latency_ms` | Histogram | Object store request latency |
| `bigrag_active_connections` | Gauge | Current active HTTP connections |
| `bigrag_namespace_count` | Gauge | Total number of namespaces |

### 24.3 Structured Logging

Already partially implemented via `tracing` and `tracing-subscriber` with `env-filter` and JSON format.

All log lines include:
- `ts`: ISO 8601 timestamp
- `level`: info/warn/error/debug
- `msg`: human-readable message
- `request_id`: per-request correlation ID
- `namespace`: namespace name (if applicable)
- `duration_ms`: operation duration
- Additional context fields per operation type

### 24.4 Tracing (Planned)

OpenTelemetry trace export for distributed tracing:
- Span per HTTP request
- Child spans for storage operations, index lookups, filter evaluation
- Configurable trace sampling rate
- Export to Jaeger, Zipkin, or OTLP-compatible collector

### 24.5 Admin Dashboard (Planned)

Built-in web admin dashboard (Next.js + shadcn/ui):
- Real-time namespace list with doc counts and storage
- Query/write rate graphs per namespace
- Cache utilization (DRAM/NVMe)
- ANN recall monitoring per namespace
- Index build status
- Slow query log
- Admin operations: compact, warm, delete namespace
- Schema browser
- Interactive query explorer

---

## 25. Security Model

### 25.1 Encryption

| Layer | Algorithm | Notes |
|-------|-----------|-------|
| In transit | TLS 1.3 | Client to bigRAG, bigRAG to object store |
| At rest | AES-256-GCM | Handled by object store (S3 SSE, GCS CMEK) |
| Application-level | Optional CMEK | Customer-managed keys via KMS (AWS KMS, GCP KMS, HashiCorp Vault) |
| API keys | Bcrypt (stored hash) | Keys never stored in plain text |

### 25.2 Network Security

- Private endpoint support: configure bigRAG to listen on private IP only
- VPC/VNet integration: deploy in private subnets
- TLS client certificates (mTLS): optional, for service-to-service auth
- Firewall rules: only API port (8080) and metrics port (9090) needed

### 25.3 Data Residency

bigRAG writes data to the object store bucket you configure. Data never leaves your chosen bucket/region unless you explicitly trigger a cross-region copy. Supports:
- EU data residency (AWS eu-central-1)
- Air-gapped deployments (MinIO on-prem)
- Sovereign cloud deployments (Azure Government, AWS GovCloud)

### 25.4 Compliance Readiness

| Standard | Status | Notes |
|---------|--------|-------|
| SOC 2 | Infrastructure responsibility | bigRAG provides audit logs + access control |
| GDPR | Supported | Namespace-per-user pattern + delete enables right-to-erasure |
| HIPAA | Supported (with TLS + encryption) | Operator must complete BAA with cloud provider |
| FedRAMP | Possible (with GovCloud) | Requires additional hardening |
| ISO 27001 | Infrastructure responsibility | -- |

### 25.5 Audit Logging (Planned)

Every API operation logged with: timestamp, API key ID, operation type, namespace, document IDs affected, source IP, request ID.

Audit log destinations: S3, Elasticsearch, Splunk, webhook.

---

## 26. Backup and Disaster Recovery

### 26.1 Object Storage as Native Backup

Because bigRAG's primary state is object storage, every write is already backed up to the object store with 99.999999999% durability (S3). The object store IS the backup.

### 26.2 Additional Backup Features (Planned)

**Namespace copy (cross-region):**
```bash
curl -X POST /v1/namespaces/prod-tenant/copy \
  -d '{"destination_namespace": "backup-tenant", "destination_bucket": "bigrag-backup-eu"}'
```

**Namespace export (Parquet/JSONL):**
```bash
curl -X POST /v1/namespaces/prod-tenant/export \
  -d '{"format": "parquet", "destination": "s3://exports/tenant.parquet"}'
```

**Scheduled backups:**
```toml
[backup]
enabled = true
schedule = "0 2 * * *"
retain_days = 7
destination_bucket = "bigrag-backups"
namespace_filter = "prod-*"
```

**Point-in-time recovery:**
WAL segments on object storage provide PITR capability. WAL segments are retained for `wal_retention_days` (default: 7).

---

## 27. Migration and Import Tools

### 27.1 Migration from turbopuffer

Drop-in API compatibility mode (Section 15) is the primary migration path. Additionally, a dedicated migration tool:

```bash
pip install bigrag-migrate
bigrag-migrate \
  --source turbopuffer \
  --source-api-key tpuf_key \
  --dest bigrag \
  --dest-url http://localhost:8080 \
  --dest-api-key br_key \
  --batch-size 10000
```

### 27.2 Migration from Other Vector Databases

| Source | Tool | Notes |
|--------|------|-------|
| turbopuffer | `bigrag-migrate --source turbopuffer` | API compat mode also works |
| Pinecone | `bigrag-migrate --source pinecone` | Requires Pinecone API key |
| Qdrant | `bigrag-migrate --source qdrant` | Collections to namespaces |
| Weaviate | `bigrag-migrate --source weaviate` | Classes to namespaces |
| Milvus | `bigrag-migrate --source milvus` | Collections to namespaces |
| pgvector | `bigrag-migrate --source pgvector` | Postgres connection string |
| Chroma | `bigrag-migrate --source chroma` | Collections to namespaces |
| Parquet files | `bigrag-migrate --source parquet` | Import from Parquet |
| JSONL files | `bigrag-migrate --source jsonl` | Import from newline-delimited JSON |

---

## 28. Plugin and Extensibility System

### 28.1 Custom Distance Functions (Planned Phase 3)

Register custom distance functions for specialized use cases:

```rust
bigrag.register_distance_fn("weighted_cosine", |a: &[f32], b: &[f32]| -> f32 {
    // custom implementation
});
```

### 28.2 Custom Tokenizers (Planned Phase 3)

Register custom tokenizers for domain-specific text processing:

```rust
bigrag.register_tokenizer("medical", |text: &str| -> Vec<String> {
    // medical NLP tokenization
});
```

### 28.3 Webhook Notifications (Planned Phase 2)

Configure webhooks for namespace events:
```toml
[webhooks]
on_write = "https://example.com/hooks/bigrag"
on_compaction_complete = "https://example.com/hooks/bigrag"
on_recall_degradation = "https://example.com/hooks/bigrag"
```

### 28.4 Embedding Sidecar (Planned Phase 3)

Optional Docker sidecar that runs embedding models locally:

```yaml
services:
  embeddings:
    image: bigrag/embeddings:latest
    environment:
      MODEL: "nomic-ai/nomic-embed-text-v1.5"
      OPENAI_COMPATIBLE_API: "true"
```

Exposes OpenAI-compatible `/v1/embeddings` endpoint for local embedding generation without external API calls.

---

## 29. Performance Targets

### 29.1 Latency Targets

| Scenario | p50 | p90 | p99 |
|----------|-----|-----|-----|
| ANN query, warm (NVMe cached) | 8ms | 15ms | 35ms |
| ANN query, hot (DRAM cached) | <1ms | 3ms | 8ms |
| ANN query, cold (object store) | 150ms | 300ms | 500ms |
| BM25 query, warm | 5ms | 20ms | 50ms |
| Hybrid query (ANN+BM25), warm | 12ms | 25ms | 60ms |
| Upsert (500KB batch) | 285ms | 370ms | 688ms |
| Delete by ID (100 docs) | 20ms | 40ms | 100ms |

### 29.2 Throughput Targets

| Metric | Target |
|--------|--------|
| Queries (per node, 8-core) | 1,000+ QPS |
| Writes (per namespace) | 10,000 docs/s at 32 MB/s |
| Namespaces (per cluster) | 10M+ |
| Documents (per namespace) | 500M+ |
| Total documents (cluster) | Trillions |

### 29.3 Scale Targets

| Dimension | Target |
|-----------|--------|
| Vector dimensions (f32) | Up to 10,752 |
| Vector dimensions (f16) | Up to 65,536 |
| Index build speed | 1M vectors/minute (f32, 768 dims) |
| Compaction throughput | 500MB/min per worker |
| Cold read throughput | Limited by object store |

### 29.4 ANN Recall Targets

| Configuration | Recall | Latency Impact |
|--------------|--------|----------------|
| `recall_target: 0.85` | ~85% | -30% latency |
| `recall_target: 0.90` | ~90% | baseline |
| `recall_target: 0.95` | ~95% | +50% latency |
| `recall_target: 1.00` | 100% | kNN (requires filter) |

---

## 30. Open Source Governance and Community

### 30.1 License

**Apache License 2.0** -- permissive, enterprise-friendly. You can:
- Use bigRAG in commercial products without open-sourcing your code
- Distribute bigRAG as part of a commercial offering
- Modify bigRAG and keep modifications private
- Only requirement: preserve copyright notices and the LICENSE file

NOTE: The workspace Cargo.toml currently says `license = "MIT"`. This needs to be changed to `license = "Apache-2.0"` to match the project intent documented in the implementation spec.

### 30.2 Repository Structure

```
bigrag/
  Cargo.toml                   # Workspace manifest
  Cargo.lock
  crates/
    bigrag-common/             # Types, config, error, schema
    bigrag-storage/            # Storage engine, backends, WAL, SST, cache, compaction
    bigrag-index/              # ANN + BM25 indexes
    bigrag-query/              # Filter DSL, ranking, query executor
    bigrag-api/                # HTTP API server (Axum)
    bigrag-server/             # Main binary
    bigrag-auth/               # API key + JWT auth (planned)
    bigrag-cli/                # CLI tool (planned)
    bigrag-bench/              # Benchmark binary (planned)
    bigrag-migrate/            # Migration tools (planned)
  sdks/
    python/                    # Python SDK (planned)
    typescript/                # TypeScript/Node SDK (planned)
    go/                        # Go SDK (planned)
    java/                      # Java SDK (planned)
    ruby/                      # Ruby SDK (planned)
  ui/                          # Admin dashboard (planned)
  docs/                        # Documentation
  docker/                      # Dockerfiles (planned)
  helm/                        # Kubernetes Helm chart (planned)
  tests/                       # Integration tests (planned)
  benches/                     # Benchmark datasets + scripts (planned)
  .github/
    workflows/                 # CI/CD (planned)
    ISSUE_TEMPLATE/            # Bug report, feature request templates (planned)
  CONTRIBUTING.md              # (planned)
  SECURITY.md                  # (planned)
  README.md                    # (planned)
```

### 30.3 Development Workflow

1. GitHub Issues for bug reports and feature requests
2. GitHub Discussions for questions and community help
3. PRs must include tests, documentation updates, and benchmark results for performance-critical changes
4. Release cadence: monthly minor releases, weekly patch releases
5. Security issues: reported via GitHub Security Advisories

### 30.4 Community Channels

- Discord: primary community chat
- GitHub Discussions: long-form questions and design discussions
- Monthly community calls: video calls open to all contributors

### 30.5 Cloud Edition (Commercial)

bigRAG Cloud is a managed version with:
- Fully managed infrastructure
- Global CDN and edge caching
- Multi-region replication
- SLA guarantees
- Unlimited support

bigRAG Cloud uses the same open-source engine. The cloud edition only adds operational tooling (auto-scaling, monitoring, billing UI).

---

## 31. Enterprise Features

### 31.1 RBAC (Role-Based Access Control)

Scoped API keys with namespace glob patterns and operation permissions (read, write, delete, schema, admin).

### 31.2 Audit Logs

Every API operation logged with timestamp, API key ID, operation type, namespace, source IP, request ID. Exportable to S3, Elasticsearch, Splunk, or webhook.

### 31.3 SSO / JWT Integration

JWKS-based JWT validation with configurable issuer, audience, and namespace claim mapping.

### 31.4 Multi-Tenancy

Namespace-based isolation with configurable cache quotas, dedicated cache pinning, and per-tenant API key scoping.

### 31.5 Encryption at Rest

Server-side encryption via object store (S3 SSE, GCS CMEK, Azure Storage Service Encryption). Optional customer-managed encryption keys via AWS KMS, GCP KMS, or HashiCorp Vault.

### 31.6 Data Residency

Deploy in any region/cloud. Data stays in the configured object store bucket and never leaves the chosen region unless explicitly copied.

### 31.7 Compliance

GDPR (namespace deletion for right-to-erasure), SOC 2 (audit logs + access control), HIPAA (TLS + encryption), FedRAMP (with GovCloud).

### 31.8 High Availability

- Stateless compute: any node can serve any namespace
- Object storage durability: 99.999999999%
- Kubernetes HPA for query and write nodes
- Anti-affinity rules for zone spread
- PodDisruptionBudget for rolling updates

---

## 32. Admin Dashboard

### 32.1 Technology

Next.js + shadcn/ui, served as static assets bundled into the main bigRAG binary or as a separate Docker container (`bigrag/ui`).

### 32.2 Features

- Real-time namespace list with doc counts, storage usage, and index status
- Query/write rate graphs per namespace (last 1h, 24h, 7d)
- Cache utilization charts (DRAM/NVMe fill levels, hit ratio)
- ANN recall monitoring per namespace with trend graphs
- Index build status and progress bars
- Slow query log with filter/sort/export
- Admin operations: trigger compaction, warm cache, delete namespace
- Schema browser: view and edit namespace schemas
- Interactive query explorer: run queries via UI with syntax highlighting
- API key management: create, list, revoke keys
- System overview: CPU, memory, disk usage, object store request rates

---

## 33. Testing Strategy

### 33.1 Unit Tests

Core engine components must have >= 80% unit test coverage. Currently implemented unit tests:
- Filter engine: Eq, NotEq, Gt, Gte, Lt, Lte, In, NotIn, Contains, And, Or, Not, null handling
- BM25 scorer: add, remove, search, scoring with TF/IDF
- Vector index: insert, search (ANN + kNN), delete, cosine distance, euclidean squared
- SSTable: build/read with no compression, LZ4, ZSTD; tombstones; range scan; bloom filter
- MemTable: put, get, delete, overwrite, drain, flush, manager
- WAL: write and flush, batch processing
- Storage backend: local roundtrip, CAS, list, path conventions
- Manifest: create, load, epoch claiming, fencing, serialization
- Block cache: hit/miss, hit ratio
- Ranking: parse ANN, BM25, order-by, Sum, saturate, decay
- Query executor: filter, vector search, attribute projection

### 33.2 Integration Tests (Planned)

Tests run against a real bigRAG instance:
- Per-test namespace with random name (never conflicts between parallel tests)
- Cleanup in test teardown (delete_namespace)
- CI-safe (run against local bigRAG in Docker)

### 33.3 Benchmark Suite (Planned)

```bash
bigrag-bench ann --dims 768 --count 100000 --metric cosine_distance --top-k 10
bigrag-bench write --batch-size 10000 --total 1000000 --dims 768
bigrag-bench query-throughput --concurrency 16 --duration 60s
```

### 33.4 Compatibility Tests (Planned)

Validate behavior parity with turbopuffer API.

---

## 34. Implementation Roadmap

### Phase 0 -- Foundation (Weeks 1-6) [MOSTLY COMPLETE]

Working bigRAG binary with basic upsert/query, local filesystem backend.

| Component | Status |
|-----------|--------|
| Local FS backend | Done |
| WAL writer + LSM structure | Done |
| SSTable format encoder/decoder | Done |
| Filter DSL parser + evaluator | Done |
| HTTP server (Axum) | Done |
| Upsert, query, delete endpoints | Done |
| Brute-force kNN baseline | Done |
| SPFresh ANN index (basic) | Done |
| BM25 inverted index (basic) | Done |
| Docker image + docker-compose | Planned |
| Python SDK v0.1 | Planned |
| README + quickstart | Planned |

### Phase 1 -- Core Feature Parity (Weeks 7-16)

Feature parity with turbopuffer's core API.

| Component | Priority |
|-----------|---------|
| S3 backend integration testing | P0 |
| MinIO backend documentation | P0 |
| Compaction (L0/L1/L2 full) | P0 |
| Conditional writes | P1 |
| Patch / delete-by-filter / patch-by-filter | P1 |
| API key management endpoints | P0 |
| DRAM cache improvements (LRU eviction) | P1 |
| NVMe L2 cache | P1 |
| Namespace management (list, copy, export) | P1 |
| Schema system (online updates) | P1 |
| TypeScript SDK | P1 |
| Go SDK | P1 |
| Prometheus metrics endpoint | P1 |
| Dockerfile | P0 |
| Helm chart (basic) | P1 |

### Phase 2 -- Advanced Features (Weeks 17-28)

Surpass turbopuffer in developer experience and features.

| Component | Priority |
|-----------|---------|
| GCS backend testing | P1 |
| Azure Blob backend testing | P1 |
| BM25 FTS v2 (MAXSCORE/WAND) | P0 |
| HNSW index (alternative to SPFresh) | P1 |
| Regex trie index | P1 |
| Multi-vector columns | P1 |
| Aggregations (count, sum, group_by, distinct) | P1 |
| Cursor-based pagination | P1 |
| Namespace copy cross-region | P1 |
| Point-in-time recovery | P2 |
| Admin dashboard (Next.js) | P1 |
| Recall monitoring + auto-tuning | P1 |
| LangChain integration | P1 |
| LlamaIndex integration | P1 |
| Java/Kotlin SDK | P2 |
| Ruby SDK | P2 |
| turbopuffer compatibility mode | P1 |
| Webhook notifications | P2 |

### Phase 3 -- Scale and Polish (Weeks 29-40)

Production-hardened, scale-tested, fully documented.

| Component | Priority |
|-----------|---------|
| Filter-aware HNSW (pre-filter ANN) | P1 |
| Document-level access control | P1 |
| JWT authentication | P1 |
| CMEK support (KMS integration) | P2 |
| Horizontal read replica scaling | P1 |
| Distributed compaction | P2 |
| Scheduled backup jobs | P2 |
| WASM embedding sidecar | P2 |
| Benchmark suite + published results | P1 |
| Geo-filtering (lat/lng radius, bounding box) | P2 |
| Streaming API (SSE) for large result sets | P2 |
| Migration tools (Pinecone, Qdrant, Weaviate) | P2 |
| Load testing (10M namespaces, 100B vectors) | P0 |
| Security audit | P0 |
| Custom distance functions | P2 |
| Custom tokenizers | P2 |

---

## 35. Competitor Self-Hosting Analysis

### 35.1 How Qdrant Does Self-Hosting

**Docker deployment:**
```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```

**Key patterns to adopt:**
- Single Docker command with volume mount for persistence
- Separate gRPC port (6334) and HTTP port (6333)
- Health check at `/healthz`
- Dashboard bundled at port 6333
- S3 snapshots for backup (but S3 is not the primary store)
- Helm chart with PVC for persistence

**Key differences from bigRAG:**
- Qdrant uses local disk as primary store, S3 only for snapshots
- Qdrant requires persistent volumes in Kubernetes
- bigRAG uses object storage as primary store, making compute truly stateless

### 35.2 How Milvus Does Docker/Kubernetes

**Docker Compose (standalone):**
- etcd for metadata
- MinIO for object storage
- Milvus standalone node
- Three containers minimum

**Kubernetes (cluster mode):**
- Helm chart with many microservices (proxy, query node, data node, index node, root coord, query coord, data coord, index coord)
- etcd, MinIO, and Pulsar/Kafka as dependencies
- Complex operational burden

**Key patterns to adopt:**
- S3-compatible object storage as primary data store (similar to bigRAG)
- Separation of query and write nodes in cluster mode

**Key patterns to AVOID:**
- Excessive microservice decomposition (Milvus has 8+ services)
- External dependencies (etcd, Pulsar/Kafka) for what should be a single-binary deployment
- bigRAG deliberately avoids external dependencies beyond the object store

### 35.3 How Weaviate Does Docker

**Docker Compose:**
```bash
docker compose up -d
```
- Single container for standalone
- Persistent volume for data
- RESTful API + gRPC
- Modules loaded as separate containers (e.g., `text2vec-transformers`)

**Key patterns to adopt:**
- Module system for optional capabilities (embeddings, reranking)
- Built-in backup to S3/GCS/Azure
- GraphQL API alongside REST

**Key differences from bigRAG:**
- Weaviate stores data on local disk (not object-storage-first)
- Weaviate's module system is heavier than bigRAG's planned sidecar approach

### 35.4 How ChromaDB Does Self-Hosting

**Docker:**
```bash
docker run -p 8000:8000 chromadb/chroma
```

**Key patterns to adopt:**
- Extreme simplicity: single command, works immediately
- Python-first SDK
- No authentication by default (easy onboarding)

**Key differences from bigRAG:**
- ChromaDB is primarily for small-scale/prototyping
- No object storage backend
- No hybrid search (BM25)
- Limited filtering
- bigRAG targets production scale that ChromaDB cannot handle

### 35.5 How LanceDB Works as Embedded

**Embedded usage (no server):**
```python
import lancedb
db = lancedb.connect("data/lancedb")
table = db.create_table("my_table", data)
results = table.search([0.1, 0.2, 0.3]).limit(10).to_list()
```

**Key patterns to adopt:**
- Embedded mode (Rust crate) for library integration
- Lance columnar format optimized for vectors (similar concept to BSF)
- Object storage support (S3, GCS, Azure)

**Key differences from bigRAG:**
- LanceDB is primarily embedded (no server mode by default)
- bigRAG is server-first with embedded as optional mode

### 35.6 Best Practices Summary for Open-Source Database Projects

1. **Single command to start:** `docker run` must work with zero configuration
2. **Persistent data via volumes:** `-v /host/path:/container/path`
3. **Health check endpoints:** `/health`, `/ready`, `/live`
4. **Prometheus metrics:** standard `/metrics` endpoint
5. **Helm chart:** official chart with sensible defaults
6. **No external dependencies for standalone mode:** single binary, no etcd/kafka/zookeeper
7. **Environment variable configuration:** every config option settable via env vars
8. **Non-root container:** security best practice
9. **Multi-arch images:** linux/amd64 + linux/arm64
10. **Versioned API:** `/v1/`, `/v2/` with backward compatibility
11. **Structured JSON logging:** machine-parseable by default
12. **Graceful shutdown:** handle SIGTERM, drain connections
13. **Documentation:** quickstart in README, full docs in `/docs` or hosted site
14. **Example applications:** demonstrate common use cases
15. **Migration tools:** make it easy to switch from competitors

---

## 36. Appendix: turbopuffer Feature Parity Matrix

| Feature | turbopuffer | bigRAG | Status |
|---------|------------|--------|--------|
| Vector ANN search (SPFresh) | Yes | Yes | Implemented |
| Vector kNN exact search | Yes | Yes | Implemented |
| BM25 full-text search | Yes | Yes | Implemented |
| Hybrid search (RRF fusion) | Yes | Yes | Partially implemented |
| Multi-query (16x parallel) | Yes | Yes | Implemented |
| Metadata filtering (full DSL) | Yes | Yes | Implemented (23 operators) |
| Array filter operators | Yes | Yes | Partially implemented |
| Regex/Glob filters | Yes | Yes | Parser done, evaluation planned |
| Phrase matching (ContainsTokenSequence) | Yes | Yes | Parser done, evaluation planned |
| Conditional writes | Yes | Yes | Planned |
| Patch by filter | Yes | Yes | Planned |
| Delete by filter | Yes | Yes | Planned |
| Column format (upsert) | Yes | Yes | Implemented |
| f16 vectors | Yes | Yes | Schema support done, storage planned |
| Multiple vector columns | Yes (beta) | Yes | Schema support done |
| Aggregations | Yes | Yes | Planned |
| Cursor pagination | Implicit | Yes | Planned |
| Namespace list with prefix | Yes | Yes | Implemented |
| Cross-region namespace copy | Yes | Yes | Planned |
| Namespace export (Parquet) | Manual | Yes | Planned |
| Recall endpoint | Yes | Yes | Implemented (stub) |
| Recall auto-tuning | Yes (auto) | Yes | Planned |
| Index state visibility | Yes | Yes | Implemented |
| Read replicas | Yes (beta) | Yes | Planned |
| Object storage backend (S3/GCS) | Yes | Yes | Implemented |
| Azure Blob backend | BYOC only | Yes | Implemented |
| MinIO backend | No | Yes | Via S3 compat |
| Local filesystem backend | No | Yes | Implemented |
| Self-hosted Docker | No | Yes | Planned |
| Open source | No | Yes | Apache 2.0 |
| HNSW index (exposed) | No | Yes | Planned |
| Filter-aware ANN (pre-filter) | No | Yes v2 | Planned Phase 3 |
| Built-in admin dashboard | Roadmap | Yes | Planned Phase 2 |
| LangChain integration | Community | Yes (official) | Planned Phase 2 |
| LlamaIndex integration | Community | Yes (official) | Planned Phase 2 |
| Geo-filtering | No | Yes v2 | Planned Phase 3 |
| Backup scheduler | Manual | Yes (built-in) | Planned Phase 2 |
| Point-in-time recovery | No | Yes | Planned Phase 2 |
| turbopuffer API compatibility | -- | Yes (compat mode) | Partially implemented |
| WASM embedding sidecar | No | Yes v2 | Planned Phase 3 |
| JWT authentication | No | Yes | Planned Phase 1 |
| API key namespace scoping | No | Yes | Planned Phase 1 |
| Document-level access control | No | Yes | Planned Phase 3 |
| Prometheus metrics | No | Yes | Planned Phase 1 |
| Structured JSON logging | No | Yes | Implemented |
| Custom distance functions | No | Yes v2 | Planned Phase 3 |
| Custom tokenizers | No | Yes v2 | Planned Phase 3 |

---

*Total features specified: 200+*
*Implementation phases: 3*
*Timeline: 40 weeks to production-ready v1*
*Current implementation state: Phase 0 mostly complete (core engine, storage, indexing, query, API)*
