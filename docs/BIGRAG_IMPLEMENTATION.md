# bigRAG — Complete Implementation Specification

> **Version:** 1.0.0-draft
> **Date:** 2026-03-28
> **Status:** Pre-implementation — engineering review required
> **License:** Apache 2.0 (open source, self-hostable)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision & Competitive Positioning](#2-product-vision--competitive-positioning)
3. [Architecture Overview](#3-architecture-overview)
4. [Core Data Model](#4-core-data-model)
5. [Storage Engine](#5-storage-engine)
6. [Indexing System](#6-indexing-system)
7. [Query Engine](#7-query-engine)
8. [Write Engine](#8-write-engine)
9. [Filter Engine](#9-filter-engine)
10. [Namespace Management](#10-namespace-management)
11. [Schema System](#11-schema-system)
12. [REST API Specification](#12-rest-api-specification)
13. [Authentication & Authorization](#13-authentication--authorization)
14. [Multi-Tenancy Architecture](#14-multi-tenancy-architecture)
15. [Client SDKs](#15-client-sdks)
16. [Self-Hosted Deployment — Docker](#16-self-hosted-deployment--docker)
17. [Kubernetes Deployment](#17-kubernetes-deployment)
18. [Configuration Reference](#18-configuration-reference)
19. [Observability & Metrics](#19-observability--metrics)
20. [Performance Targets & Benchmarks](#20-performance-targets--benchmarks)
21. [Security Model](#21-security-model)
22. [Backup & Recovery](#22-backup--recovery)
23. [Migration & Import Tools](#23-migration--import-tools)
24. [Testing Strategy](#24-testing-strategy)
25. [Open Source Governance & Community](#25-open-source-governance--community)
26. [Implementation Roadmap](#26-implementation-roadmap)
27. [Engineering Team Structure](#27-engineering-team-structure)
28. [Appendix: turbopuffer Feature Parity Matrix](#28-appendix-turbopuffer-feature-parity-matrix)

---

## 1. Executive Summary

**bigRAG** is an open-source, self-hostable vector and full-text search database purpose-built for Retrieval-Augmented Generation (RAG) workloads. It is the open-source answer to turbopuffer: a serverless vector store that today costs a minimum of $64/month with no self-hosted option and no open-source license.

bigRAG provides:

- **Zero licensing cost** — Apache 2.0, run it anywhere
- **Object-storage-first architecture** — S3, GCS, Azure Blob, MinIO, or local disk
- **Full turbopuffer API compatibility** — drop-in replacement for existing turbopuffer clients
- **Hybrid search** — dense vector (ANN), sparse (BM25), and metadata filters in a single query
- **Unlimited namespaces** — one per tenant, zero marginal cost
- **Docker + Kubernetes native** — single binary, `docker run bigrag/bigrag`
- **Sub-10ms warm query latency** — matching turbopuffer's warm-tier performance
- **Written in Rust** — safe, fast, memory-efficient

### Target Users

| User | Pain Point Solved |
|------|-------------------|
| SaaS startups | Can't afford $64+/month minimum; need per-tenant isolation |
| Enterprise engineering teams | Need data residency / BYOC without $4,096/month Enterprise plan |
| AI/RAG developers | Want a local dev DB matching production semantics |
| Open-source projects | No production-grade open-source vector DB with full hybrid search + object storage backend |
| Platform teams | Want to embed a vector search engine in their own product |

---

## 2. Product Vision & Competitive Positioning

### 2.1 What turbopuffer Does Right (and We Match)

After deep analysis of turbopuffer's architecture and customer case studies (Cursor, Notion, Linear, Superhuman), the following features are non-negotiable:

1. **Object-storage as primary state** — Not an afterthought. Object storage IS the WAL, IS the index store, IS the backup. This enables stateless compute nodes and massive cost reduction ($0.02/GB on S3 vs $2+/GB for in-memory).
2. **Unlimited namespaces at near-zero marginal cost** — Turbopuffer serves Cursor (10M namespaces), Notion (1M), Linear (1.5M). bigRAG must scale the same way.
3. **Hybrid search in one call** — BM25 + ANN + metadata filters in a single API request.
4. **Strong consistency by default** — Not eventual consistency as a trap; reads immediately reflect committed writes.
5. **Multi-query per request** — Up to 16 parallel query vectors in a single HTTP request.

### 2.2 Where bigRAG Differentiates

| Feature | turbopuffer | bigRAG |
|---------|------------|--------|
| License | Proprietary SaaS | Apache 2.0 |
| Self-hosted | Not available | First-class Docker/K8s |
| Minimum cost | $64/month | $0 |
| Open source | SDKs only | Entire engine |
| Local dev | No (pay for API) | `docker run bigrag/bigrag` |
| Storage backends | AWS S3, GCS (managed) | S3, GCS, Azure Blob, MinIO, local FS |
| Embedding generation | External only | Built-in embedding server (optional) |
| HNSW tuning | Hidden/auto | Exposed (`ef_construction`, `M`, `ef_search`) |
| Recall tuning | No user control | Full HNSW param exposure |
| Cold start | ~400ms | Target <200ms with prefetch hints |
| Filter-aware ANN | Post-filter only | Pre-filter HNSW (planned v2) |
| WASM embedding | No | Yes (run Nomic/BGE/E5 in-process) |
| Dashboard | PHPMyAdmin-style (roadmap) | Day-1 built-in web UI |
| Pricing model | Per-query metered | Self-hosted: free; Cloud edition: usage-based |

### 2.3 Competitive Landscape

```
                 Self-Hosted?  Open Source?  Object Storage?  Hybrid Search?  Multi-tenant?
turbopuffer          No            No             Yes               Yes           Yes (∞ ns)
bigRAG               YES           YES            YES               YES           YES
Qdrant               Yes           Yes            Partial           Partial       Limited
Weaviate             Yes           Yes            No                Yes           Limited
Milvus               Yes           Yes            Yes (Kafka WAL)   Partial       Yes
pgvector             Yes           Yes            No                No            Per-schema
Chroma               Yes           Yes            No                Partial       Namespace
Pinecone             No            No             Yes               Yes           Limited
```

**bigRAG's moat:** The only fully open-source vector database with an object-storage-first architecture + full BM25 hybrid search + unlimited namespaces + self-hosted Docker support.

---

## 3. Architecture Overview

### 3.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            bigRAG Cluster                                │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      API Gateway Layer                           │   │
│  │  HTTP/1.1 + HTTP/2  ·  REST JSON  ·  Auth (API Key / JWT)       │   │
│  │  Rate limiting  ·  Request routing  ·  Multi-query dispatch      │   │
│  └────────────────────────────────┬─────────────────────────────────┘   │
│                                   │                                      │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                      Query & Write Router                        │   │
│  │  Namespace resolver  ·  Shard router  ·  Load balancer           │   │
│  └────────┬──────────────────────────────────────────┬─────────────┘   │
│           │                                          │                   │
│  ┌────────▼──────────┐                  ┌────────────▼──────────────┐   │
│  │   Query Workers   │                  │     Write Workers          │   │
│  │  (read replicas)  │                  │  (namespace WAL writers)   │   │
│  │                   │                  │                            │   │
│  │  ANN search       │                  │  Upsert / Patch / Delete   │   │
│  │  BM25 search      │                  │  Conditional writes        │   │
│  │  Hybrid fusion    │                  │  Batch coalescer           │   │
│  │  Filter engine    │                  │  Schema validator          │   │
│  └────────┬──────────┘                  └────────────┬──────────────┘   │
│           │                                          │                   │
│  ┌────────▼──────────────────────────────────────────▼──────────────┐   │
│  │                      Storage Abstraction Layer                   │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │   │
│  │  │  L1: DRAM   │  │  L2: NVMe    │  │  L3: Object Storage  │    │   │
│  │  │  Hot cache  │  │  SSD cache   │  │  S3/GCS/MinIO/Local  │    │   │
│  │  │  <1ms       │  │  <10ms       │  │  ~100-500ms cold     │    │   │
│  │  └─────────────┘  └──────────────┘  └──────────────────────┘    │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Background Services                           │   │
│  │  Index compactor  ·  Cache warming  ·  Recall monitor            │   │
│  │  Namespace janitor  ·  Stats aggregator  ·  Backup scheduler     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Deployment Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Standalone** | Single binary, all components in one process | Dev, small deployments |
| **Clustered** | Separate query and write nodes | Production, horizontal scale |
| **Embedded** | Library mode (Rust crate) | Embedded in other applications |
| **Serverless** | Fly.io, Railway, Render deploy | Zero-ops cloud |

### 3.3 Key Design Principles

1. **Object storage is the only source of truth.** All durability comes from the object store. Compute nodes are 100% stateless and replaceable.
2. **LSM-tree semantics over object storage.** Writes append new segment files; background compaction merges segments; the WAL directory is the primary log.
3. **Namespace = prefix on object storage.** A namespace named `tenant-abc` maps to prefix `ns/tenant-abc/` in the bucket. No database migration required for new tenants.
4. **Stateless compute enables unlimited scale-out.** Any query node can serve any namespace without pre-routing. Failover is instantaneous.
5. **Minimize object storage round trips.** The #1 latency driver for cold reads. bigRAG's index format (bigRAG Segment Format, BSF) is designed to answer ANN queries in ≤4 S3 GET requests.
6. **Recall ≥ 90% at 1,000 QPS.** ANN index must achieve 90%+ recall at real production load, not just synthetic benchmarks.

---

## 4. Core Data Model

### 4.1 Hierarchy

```
Organization
└── Namespace (unlimited)
    ├── Schema (evolves online)
    │   ├── Vector columns (1..N)
    │   ├── Attribute columns (0..256)
    │   └── FTS indexes (0..N)
    └── Documents (0..500M per namespace)
        ├── id (required, unique)
        ├── vector (optional, must match schema)
        └── attributes (key-value, typed)
```

### 4.2 Document

A document is the atomic unit of storage and retrieval. Every document:
- Has a unique `id` within its namespace
- May have one or more vector columns
- May have zero or more typed attribute columns
- Is versioned internally (MVCC-lite for conditional writes)

**Document wire format (JSON):**

```json
{
  "id": "doc-123",
  "vector": [0.1, 0.2, 0.3, 0.4],
  "attributes": {
    "title": "Introduction to RAG",
    "category": "ml",
    "published_at": "2024-01-15T10:00:00Z",
    "score": 4.7,
    "tags": ["rag", "llm", "retrieval"],
    "public": true
  }
}
```

**ID types:**
- `uint64`: 64-bit unsigned integer (most compact)
- `uuid`: 128-bit UUID in standard hyphenated string format
- `string`: UTF-8 string, max 64 bytes

**Vector representation:**
- JSON array of f32 floats: `[0.1, 0.2, ...]`
- Base64-encoded little-endian f32: `"base64:AAAA..."` (bandwidth optimized)
- Base64-encoded little-endian f16: `"base64f16:..."` (50% storage reduction)

### 4.3 Attribute Types

| Type | Description | Examples | Filter ops |
|------|-------------|---------|-----------|
| `string` | UTF-8 text, max 8 MiB | `"hello"` | Eq, NotEq, In, NotIn, Contains, Glob, Regex |
| `int` | Signed 64-bit integer | `-42`, `0`, `999` | Eq, NotEq, Lt, Lte, Gt, Gte, In, NotIn |
| `uint` | Unsigned 64-bit integer | `0`, `4294967295` | Eq, NotEq, Lt, Lte, Gt, Gte, In, NotIn |
| `float` | IEEE 754 f64 | `3.14`, `-1.5e10` | Eq, NotEq, Lt, Lte, Gt, Gte |
| `bool` | Boolean | `true`, `false` | Eq, NotEq |
| `uuid` | UUID v4/v7 | `"550e8400-..."` | Eq, NotEq, In, NotIn |
| `datetime` | ISO 8601 UTC | `"2024-01-15T10:00:00Z"` | Eq, NotEq, Lt, Lte, Gt, Gte |
| `[]string` | Array of strings | `["a","b","c"]` | Contains, ContainsAny, ContainsAll, AnyEq, AnyGlob |
| `[]int` | Array of ints | `[1, 2, 3]` | AnyEq, AnyLt, AnyLte, AnyGt, AnyGte, Contains |
| `[]uint` | Array of uints | `[10, 20]` | AnyEq, AnyLt, AnyLte, AnyGt, AnyGte |
| `[]float` | Array of floats | `[1.5, 2.7]` | AnyEq, AnyLt, AnyLte, AnyGt, AnyGte |
| `[]bool` | Array of bools | `[true, false]` | AnyEq, Contains |
| `[]uuid` | Array of UUIDs | `["uuid1", "uuid2"]` | Contains, ContainsAny, ContainsAll |
| `[]datetime` | Array of datetimes | `["2024-01-01", ...]` | AnyLt, AnyGt, AnyLte, AnyGte |

All attributes are nullable. A null value is distinct from the absence of the attribute.

**Filterable vs. Non-filterable:**
- Default: `filterable: true` — attribute has an index, supports sorting and filtering
- `filterable: false` — 50% storage discount, attribute is stored as opaque bytes, cannot be filtered/sorted

### 4.4 Namespace

A namespace is an isolated container with its own:
- Schema (vector dimension, distance metric, attribute types)
- ANN index
- BM25 inverted index (per FTS-enabled attribute)
- Attribute indexes (B-tree for range, hash for equality, regex trie for patterns)
- Object storage prefix: `{bucket}/{namespace_id}/`

**Namespace naming:**
- Pattern: `[A-Za-z0-9\-_\.]{1,128}`
- Recommended multi-tenant pattern: `{table}_{tenant_id}` or `{env}_{table}_{tenant_id}`
- The prefix pattern enables compliance operations: list all namespaces for `user-123` with prefix `*_user-123`

---

## 5. Storage Engine

### 5.1 Storage Hierarchy

bigRAG uses a three-tier storage hierarchy identical to turbopuffer's proven model:

```
Tier 1 — DRAM (L1)
  Size: Configurable (default: 20% of available RAM)
  Latency: <1ms
  Eviction: LRU with frequency counter (LIRS variant)
  Contents: Hot namespace ANN indexes, BM25 posting lists, attribute indexes

Tier 2 — NVMe SSD (L2)
  Size: Configurable (default: all available NVMe)
  Latency: <10ms (after initial page fault)
  Eviction: LRU per namespace, with namespace TTL
  Contents: Warm namespace segments (BSF files), decompressed vectors

Tier 3 — Object Storage (L3)
  Size: Unlimited
  Latency: ~50-500ms (cold read, network dependent)
  Durability: Provider SLA (99.999999999%)
  Contents: WAL segments, merged segment files (BSF), schema manifests
```

### 5.2 bigRAG Segment Format (BSF)

bigRAG defines its own binary segment format (BSF) optimized for:
- Answering ANN queries in ≤4 object storage GET requests
- Columnar layout for efficient metadata filtering
- Integrated compression per column type

**BSF File Layout:**

```
┌──────────────────────────────────────────────────────┐
│ BSF Header (64 bytes)                                 │
│   Magic: 0x42534601 ("BSF\x01")                      │
│   Version: u16                                        │
│   Flags: u32 (compression, encryption, multi-vector) │
│   Doc count: u64                                      │
│   Segment ID: u128 (UUIDv7)                          │
│   Min doc ID / Max doc ID                            │
│   Created at: i64 (unix ms)                          │
├──────────────────────────────────────────────────────┤
│ Column Directory (variable)                          │
│   For each column:                                   │
│     - Column name (length-prefixed string)           │
│     - Column type (u8)                               │
│     - Offset in file (u64)                           │
│     - Length (u64)                                   │
│     - Compression codec (u8): None/LZ4/ZSTD/Snappy  │
├──────────────────────────────────────────────────────┤
│ ID Column                                            │
│   Sorted array of document IDs                       │
│   Enables binary search O(log n) by ID               │
├──────────────────────────────────────────────────────┤
│ Vector Columns (one per vector attribute)            │
│   Quantized vectors: RaBitQ binary (1 bit/dim)       │
│   Full-precision residuals: f32 or f16               │
│   Centroid table: cluster centroids for SPFresh       │
│   Cluster assignments: doc -> cluster mapping         │
├──────────────────────────────────────────────────────┤
│ Attribute Columns (one per filterable attribute)     │
│   B-tree index for range queries                     │
│   Bloom filter for existence checks                  │
│   Dictionary encoding for low-cardinality strings    │
├──────────────────────────────────────────────────────┤
│ BM25 Inverted Index (per FTS attribute)              │
│   Vocabulary: sorted term → {idf, posting_offset}   │
│   Posting lists: sorted doc IDs + tf scores          │
│   Skip lists: MAXSCORE/WAND acceleration             │
├──────────────────────────────────────────────────────┤
│ Footer                                               │
│   CRC32C checksum of all preceding data              │
│   Metadata JSON blob (arbitrary key-value)           │
└──────────────────────────────────────────────────────┘
```

### 5.3 LSM-Tree Over Object Storage

bigRAG implements an LSM-tree (Log-Structured Merge-tree) built on object storage:

**Object storage layout per namespace:**

```
{bucket}/
└── ns/{namespace_id}/
    ├── manifest.json          # Current namespace schema + segment list
    ├── manifest.json.prev     # Previous manifest (rollback)
    ├── wal/
    │   ├── 0000000000001.wal  # WAL segment 1
    │   ├── 0000000000002.wal  # WAL segment 2
    │   └── ...
    ├── segments/
    │   ├── L0/                # Freshly flushed, small segments
    │   │   ├── {uuid}.bsf
    │   │   └── ...
    │   ├── L1/                # Compacted, medium segments
    │   │   └── {uuid}.bsf
    │   └── L2/                # Fully compacted, large segments
    │       └── {uuid}.bsf
    └── stats/
        └── {date}.json        # Daily namespace statistics
```

**Write flow:**

```
Client write request
       │
       ▼
Batch coalescer (max 1s or 512MB)
       │
       ▼
WAL writer (appends to wal/{seq}.wal on object storage)
       │          ← HTTP 200 returned to client here (durable)
       ▼
Async indexer (background):
  - Decompress WAL segment
  - Build BSF segment (L0)
  - Upload to segments/L0/{uuid}.bsf
  - Update manifest.json (atomic PUT with CAS)
  - Trigger compaction if L0 count > threshold
       │
       ▼
Compactor (background):
  - Merge L0 segments → L1 segment
  - Merge L1 segments → L2 segment
  - Delete obsolete segments
  - Update manifest
```

**Read flow:**

```
Query request
       │
       ▼
Check L1 cache (DRAM) → HIT: return
       │ MISS
       ▼
Check L2 cache (NVMe) → HIT: return + promote to L1
       │ MISS
       ▼
Enumerate manifest.json (1 GET)
       │
       ▼
Fetch relevant BSF column sections (1-4 GETs)
  - For ANN: centroid table → candidate clusters → vector data
  - For BM25: posting lists for query terms
  - For filters: attribute B-tree pages
       │
       ▼
Populate L2 cache (NVMe)
Populate L1 cache (DRAM for hot namespaces)
       │
       ▼
Return results
```

### 5.4 WAL Design

- Each namespace has its own WAL stream, independent of other namespaces.
- WAL entries are write-ahead: the client receives HTTP 200 only after the WAL segment is durably committed to object storage.
- WAL segments are immutable after commitment. Conflicts are resolved by last-write-wins or conditional writes.
- **Max 1 WAL entry per second per namespace** (rate-limited by object storage PUT consistency). Concurrent writes within the 1-second window are coalesced into a single WAL entry.
- **Max WAL batch size: 512 MB**

**WAL segment format:**

```
WAL Segment Header:
  - Magic: 0x574C0001
  - Namespace ID
  - Sequence number (monotonically increasing per namespace)
  - Previous sequence hash (chain integrity)
  - Timestamp (unix ms)

WAL Entries (repeated):
  - Operation type: UPSERT | PATCH | DELETE | DELETE_BY_FILTER | PATCH_BY_FILTER
  - Document count
  - Compressed payload (LZ4)
  - Per-entry checksum (CRC32C)

WAL Segment Footer:
  - Entry count
  - Total uncompressed bytes
  - Segment CRC32C
```

### 5.5 Compaction Strategy

bigRAG uses a **leveled compaction** strategy with size-tiered merging at L0:

| Level | Target size | Trigger | Merge strategy |
|-------|------------|---------|----------------|
| L0 | < 64 MB | Every flush | Size-tiered: merge 4+ L0 segments |
| L1 | 64 MB – 512 MB | L0→L1 promotion | Sorted merge |
| L2 | 512 MB – 2 GB | L1→L2 promotion | Full merge with re-indexing |

**Compaction is namespace-local.** Compacting namespace A never touches namespace B.

**Delete handling:** Deleted document IDs are tracked in a tombstone set per segment. During compaction, tombstones are applied and the affected vectors are removed from the merged segment.

---

## 6. Indexing System

### 6.1 ANN Vector Index

#### 6.1.1 Algorithm Selection

bigRAG implements **SPFresh** (Streaming Partition-based Fresh index) as the primary ANN algorithm, matching turbopuffer's proven production choice. SPFresh is purpose-built for object-storage-first architectures:

- **Graph-free design** — avoids HNSW's requirement to traverse thousands of graph nodes (each potentially requiring a separate object store read)
- **Centroid-based** — partitions vectors into clusters; queries fetch the top-k centroids then refine within those clusters
- **Incremental updates** — new vectors are assigned to existing clusters without full index rebuild
- **Low read amplification** — typically 3-4 object store GET requests per query (vs. 20-100+ for HNSW on object storage)

#### 6.1.2 SPFresh Implementation

**Index structure:**

```
SPFresh Index
├── Centroid table (K centroids, each dimension D)
│   K = sqrt(N) initially, scaled dynamically
│   Stored compressed: K × D × f32 bytes
├── Cluster assignments (doc_id → cluster_id mapping)
│   Stored as sorted array: 8 bytes per document
├── Per-cluster vector store
│   Vectors in each cluster stored contiguously
│   Compression: RaBitQ (1 bit/dim) + f16 residuals
└── SPFresh candidate list (for incremental updates)
    Tracks recently added vectors not yet absorbed into clusters
```

**Query path:**

```
1. Encode query vector with binary quantization (fast dot products)
2. Compute approximate distance from query to ALL centroids (fast, K << N)
3. Select top nprobe centroids (nprobe = max(16, sqrt(K)))
4. Fetch vector data for selected clusters from object storage
5. Re-rank candidates using full-precision f32/f16 vectors
6. Apply metadata filters
7. Return top-k results
```

**HNSW option (alternative):** For deployments where data is fully NVMe/DRAM resident (small-scale or high-budget), bigRAG also supports HNSW with configurable parameters:

```yaml
vector_index:
  type: hnsw           # or spfresh (default)
  M: 16                # connections per layer (default: 16)
  ef_construction: 200  # search width during build (default: 200)
  ef_search: 64        # search width during query (default: 64)
```

HNSW provides higher recall at higher memory cost. Use SPFresh when object storage is the primary backend; use HNSW when data fits in NVMe.

#### 6.1.3 Distance Metrics

| Metric | API name | Formula | Use case |
|--------|----------|---------|---------|
| Cosine distance | `cosine_distance` | 1 - (a·b)/(|a||b|) | Normalized embeddings (OpenAI, Cohere) |
| Euclidean squared | `euclidean_squared` | Σ(aᵢ-bᵢ)² | Unnormalized embeddings |
| Dot product | `dot_product` | -(a·b) | Matryoshka, learned metrics |
| Hamming | `hamming` | popcount(a XOR b) | Binary vectors |

**Default:** `cosine_distance` (matches most embedding model output)

#### 6.1.4 Vector Quantization

bigRAG supports multiple quantization levels to trade precision for cost:

| Format | Storage | Recall impact | Use when |
|--------|---------|--------------|---------|
| `f32` | 4 bytes/dim | Baseline (100%) | Max precision, smaller datasets |
| `f16` | 2 bytes/dim | ~99% | 2x storage reduction, recommended default |
| `int8` | 1 byte/dim | ~97% | 4x reduction, large datasets |
| `binary` | 1 bit/dim | ~90% | 32x reduction, ultra-scale |

RaBitQ is used for binary quantization — it maintains higher recall than naive binary quantization by using multi-bit residuals for top candidates.

#### 6.1.5 Recall Monitoring

bigRAG provides a built-in recall monitor:

- **Endpoint:** `GET /v1/namespaces/{ns}/recall`
- **Method:** Periodically samples production queries, runs the same query exhaustively (kNN), and computes recall@k
- **Automated tuning:** If recall drops below threshold (default 90%), bigRAG automatically increases `nprobe` and triggers a background index rebuild
- **Manual override:** Users can set `"recall_target": 0.95` in namespace config

### 6.2 Full-Text Search Index (BM25)

#### 6.2.1 BM25 Implementation

bigRAG implements BM25+ (with MAXSCORE/WAND acceleration) for full-text search:

**Scoring formula:**

```
BM25(q, d) = Σ_t∈q  IDF(t) × [ (tf(t,d) × (k1 + 1)) / (tf(t,d) + k1 × (1 - b + b × |d|/avgdl)) ]

Parameters:
  k1 (default: 1.2)  — term frequency saturation
  b  (default: 0.75) — document length normalization
  k3 (default: 8.0)  — query term frequency weighting (BM25+ extension)
```

**Tokenization pipeline:**

```
Input text
    │
    ▼
Unicode normalization (NFC)
    │
    ▼
Tokenizer selection:
  word_v3 (default): Unicode word boundary segmentation
  ngram: character n-gram (for CJK, no-space languages)
  whitespace: simple space split
    │
    ▼
Case folding (configurable, default: lowercase)
    │
    ▼
ASCII folding (configurable, default: off)
    │
    ▼
Stop word removal (configurable, default: off)
  Supported languages: english, french, german, spanish,
                       portuguese, italian, dutch, russian,
                       chinese, japanese, korean
    │
    ▼
Stemming (configurable, default: off)
  Snowball stemmer for supported languages
    │
    ▼
Max token length filter (default: 39 bytes)
    │
    ▼
Token stream → inverted index update
```

#### 6.2.2 Inverted Index Structure

```
Inverted Index (per FTS-enabled attribute):
├── Vocabulary (sorted trie or B-tree)
│   term → {
│     doc_freq: u32,          # number of documents containing term
│     idf: f32,               # precomputed IDF score
│     posting_list_offset: u64 # offset in posting file
│   }
├── Posting lists (variable length)
│   For each term:
│   [doc_id: u64, tf: f16, positions: [u16...]] × doc_freq
│   Encoded with: Frame-of-Reference + BitPacking (SIMD-accelerated)
├── Skip lists (for MAXSCORE/WAND)
│   Sparse index into posting lists: every 128th entry
│   Enables skipping entire blocks of low-scoring documents
└── Field lengths
    [doc_id: u64, field_length: u32]
    Used for length normalization in BM25
```

#### 6.2.3 FTS v2 Architecture (from turbopuffer research)

bigRAG's FTS engine is modeled after turbopuffer's FTS v2 (launched December 2025, up to 20x faster than v1):

Key improvements over naive BM25:
1. **Dynamic bit-set encoding** for high-frequency terms (>1% document frequency) — stores matching doc IDs as a dense bitmap, enabling fast boolean AND operations
2. **MAXSCORE algorithm** — partitions query terms into essential (must process) and non-essential (can skip). Query `"pop singer songwriter"` may be faster than `"pop singer"` because adding `"songwriter"` makes it the essential term with shorter posting list
3. **Per-shard WAND scoring** — block-max optimization; skips posting list blocks whose max score can't contribute to top-k
4. **Vectorized scoring** (AVX2/NEON) — processes 8 posting list entries simultaneously

**Performance characteristics** (200M document dataset):
- Simple single-term query: 3-5ms
- Multi-term query (3-5 terms): 5-15ms
- High-frequency term query ("of", "the"): 30-100ms with WAND optimization
- Top-k scaling: multiplying k by 10 increases latency ~65% (sub-linear)

#### 6.2.4 FTS Schema Configuration

```json
{
  "schema": {
    "content": {
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
      },
      "filterable": false
    }
  }
}
```

**FTS attributes are NOT filterable by default** (they use inverted indexes, not B-tree indexes). Combine `full_text_search: true` + `filterable: true` if you need both BM25 search and equality filtering on the same attribute.

### 6.3 Attribute Indexes

For filterable attributes, bigRAG maintains secondary indexes:

| Index type | Attribute types | Operations |
|-----------|----------------|------------|
| **B-tree** | int, uint, float, datetime | Lt, Lte, Gt, Gte, range scans |
| **Hash index** | string, uuid, bool | Eq, NotEq, In, NotIn |
| **Bloom filter** | All types | Fast NOT EXISTS check |
| **Bitmap index** | bool, low-cardinality string | AND/OR across large sets |
| **Regex trie** | string | Glob, Regex, IGlob patterns |
| **Inverted list** | []string, []uuid | Contains, ContainsAny, ContainsAll |

#### Online Schema Updates

bigRAG supports **online, in-place schema changes** without downtime:

- **Adding `filterable: true`** to an existing non-filterable attribute: triggers background index build. Queries on that attribute return HTTP 202 (Accepted) until index is ready, then switch to indexed queries automatically.
- **Changing FTS parameters** (e.g., stemming, language): triggers background FTS index rebuild. Queries continue using the old index until the rebuild completes.
- **Changing `filterable: false`** on an existing filterable attribute: drops the index immediately. Queries on that attribute return an error until the next write.
- **Changing attribute type**: requires namespace export + re-import (breaking change, not supported online).

---

## 7. Query Engine

### 7.1 Query DSL

bigRAG implements a JSON-based query DSL compatible with turbopuffer's API.

**Full query request structure:**

```json
{
  "rank_by": ["vector", "ANN", [0.1, 0.2, 0.3]],
  "filters": ["And",
    ["category", "Eq", "ml"],
    ["published_at", "Gt", "2024-01-01T00:00:00Z"],
    ["tags", "ContainsAny", ["rag", "llm"]]
  ],
  "limit": {
    "total": 20,
    "per": {
      "attribute": "category",
      "limit": 5
    }
  },
  "include_vectors": false,
  "include_attributes": ["title", "category", "score"],
  "consistency": "strong",
  "distance_cutoff": 0.4,
  "recall_target": 0.9
}
```

### 7.2 Rank-By Modes

#### 7.2.1 Vector ANN (Approximate Nearest Neighbor)

```json
"rank_by": ["vector", "ANN", [0.1, 0.2, 0.3, ...]]
```

- Queries the SPFresh (or HNSW) index
- Returns documents ordered by distance ascending (closer = better)
- Recall is approximate (configurable target, default ≥90%)
- Fast: typically 8-40ms warm latency

#### 7.2.2 Vector kNN (Exact)

```json
"rank_by": ["vector", "kNN", [0.1, 0.2, 0.3, ...]]
```

- Exhaustive scan of all vectors in the filtered set
- 100% recall guarantee
- **Requires a filter** (enforced to prevent full-namespace exhaustive scan on large datasets)
- Appropriate for: small filtered subsets, recall testing, compliance workloads

#### 7.2.3 BM25 Full-Text Search

```json
"rank_by": ["content", "BM25", "what is retrieval augmented generation"]
```

- Queries the BM25 inverted index on the specified FTS attribute
- Returns documents ordered by BM25 score descending
- Query is tokenized using the same pipeline as indexing

#### 7.2.4 Attribute Ordering

```json
"rank_by": ["published_at", "Desc"]
```

- Returns documents ordered by attribute value
- Supports `"Asc"` and `"Desc"`
- Requires `filterable: true` on the attribute
- Can be combined with filters for "latest N documents matching X"

### 7.3 Hybrid Search (Multi-Query)

bigRAG supports multi-query requests: up to **16 rank_by expressions** in a single API call, executed in parallel and fused.

**Multi-query request format:**

```json
{
  "queries": [
    {
      "rank_by": ["vector", "ANN", [0.1, 0.2, ...]],
      "limit": {"total": 100}
    },
    {
      "rank_by": ["content", "BM25", "introduction to rag"],
      "limit": {"total": 100}
    }
  ],
  "fusion": {
    "method": "rrf",
    "k": 60
  },
  "filters": ["category", "Eq", "ml"],
  "limit": {"total": 10},
  "include_attributes": ["title", "score"]
}
```

**Fusion methods:**

| Method | Formula | When to use |
|--------|---------|-------------|
| `rrf` | score = Σ 1/(k + rank_i) | Default; robust, no calibration needed |
| `linear` | score = w1*score1 + w2*score2 | When you have calibrated weights |
| `dbsf` | Distribution-based score fusion | For normalized scores from different systems |

**Reciprocal Rank Fusion (RRF):**

```
RRF(d, queries, k=60) = Σ_q∈queries  1 / (k + rank_q(d))
```

k=60 is the default constant. Higher k reduces the influence of top ranks; lower k amplifies it.

### 7.4 Pagination

**Limit parameters:**

```json
{
  "limit": {
    "total": 100,
    "per": {
      "attribute": "category",
      "limit": 5
    }
  }
}
```

- `limit.total`: Maximum total results (max 10,000)
- `limit.per`: Constrain results to at most N per unique value of an attribute (faceted top-k)

**Cursor-based pagination** for browsing beyond `limit.total`:

```json
{
  "rank_by": ["published_at", "Desc"],
  "limit": {"total": 100},
  "cursor": "eyJsYXN0X2lkIjogIjEyMyIsICJ0cyI6IDEyMzQ1Nn0="
}
```

Response includes `"next_cursor"` if more results exist.

### 7.5 Result Response Format

```json
{
  "results": [
    {
      "id": "doc-123",
      "dist": 0.15,
      "attributes": {
        "title": "Introduction to RAG",
        "category": "ml"
      },
      "vector": null
    }
  ],
  "next_cursor": null,
  "billing": {
    "queried_bytes": 52428800,
    "returned_bytes": 2048
  },
  "performance": {
    "server_ms": 8,
    "index_ms": 5,
    "filter_ms": 1,
    "network_ms": 2
  },
  "recall_estimate": 0.94
}
```

### 7.6 Aggregations

bigRAG supports aggregations in queries:

```json
{
  "aggregations": [
    {"type": "count"},
    {"type": "sum", "attribute": "score"},
    {"type": "min", "attribute": "published_at"},
    {"type": "max", "attribute": "published_at"},
    {"type": "group_by", "attribute": "category", "limit": 100},
    {"type": "distinct", "attribute": "author"}
  ],
  "filters": ["public", "Eq", true]
}
```

Aggregations run concurrently with the vector/BM25 search. The response includes both ranked results AND aggregation results in a single API call.

---

## 8. Write Engine

### 8.1 Upsert

`POST /v1/namespaces/{namespace}/documents`

Upserts (insert or replace) documents in column-oriented or row-oriented format.

**Row format (JSON array):**

```json
{
  "documents": [
    {
      "id": "doc-1",
      "vector": [0.1, 0.2, 0.3],
      "attributes": {"title": "Doc 1", "score": 4.5}
    },
    {
      "id": "doc-2",
      "vector": [0.4, 0.5, 0.6],
      "attributes": {"title": "Doc 2", "score": 3.8}
    }
  ]
}
```

**Column format (bandwidth optimized):**

```json
{
  "columns": {
    "ids": ["doc-1", "doc-2"],
    "vectors": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    "attributes": {
      "title": ["Doc 1", "Doc 2"],
      "score": [4.5, 3.8]
    }
  }
}
```

Column format is more bandwidth-efficient for large batches (avoids repeating key names per document).

**Response:**

```json
{
  "rows_affected": 2,
  "rows_upserted": 2,
  "rows_patched": 0,
  "rows_deleted": 0,
  "billing": {"write_bytes": 256},
  "performance": {"server_ms": 285}
}
```

### 8.2 Patch (Partial Update)

Patch updates specific attributes without replacing the entire document. Vectors are NOT replaced unless explicitly included.

```json
{
  "patches": [
    {
      "id": "doc-1",
      "attributes": {"score": 4.8, "updated_at": "2024-03-01T00:00:00Z"}
    }
  ]
}
```

**Patch semantics:**
- Only specified attributes are updated
- Unspecified attributes are preserved as-is
- Setting an attribute to `null` explicitly removes it
- Vector is NOT changed unless included in the patch

### 8.3 Delete

**Delete by ID:**

```json
{
  "deletes": ["doc-1", "doc-2", "doc-3"]
}
```

**Delete by filter (`delete_by_filter`):**

```json
{
  "delete_by_filter": {
    "filter": ["category", "Eq", "deprecated"],
    "max_affected": 5000000,
    "allow_partial": false
  }
}
```

- Max 5,000,000 documents per `delete_by_filter` request
- `allow_partial: true` succeeds even if more documents match (deletes up to `max_affected`)
- Response includes `"rows_remaining": true` if additional matching documents exist

### 8.4 Patch by Filter (`patch_by_filter`)

Updates attributes on all documents matching a filter:

```json
{
  "patch_by_filter": {
    "filter": ["status", "Eq", "pending"],
    "attributes": {"status": "processed", "processed_at": "2024-03-01T12:00:00Z"},
    "max_affected": 50000,
    "allow_partial": false
  }
}
```

- Max 50,000 documents per `patch_by_filter` request (vector attributes cannot be patched by filter)
- Billed as one query cost + write cost proportional to affected documents

### 8.5 Conditional Writes

Conditional writes apply an operation only when a condition is met at write time. Uses the filter DSL plus a special `$ref_new` reference:

**Optimistic locking (version check):**

```json
{
  "documents": [
    {
      "id": "doc-1",
      "attributes": {"version": 5, "content": "updated"}
    }
  ],
  "condition": ["version", "Lt", {"$ref_new": "version"}]
}
```

`$ref_new` refers to the value in the incoming write. The condition `["version", "Lt", {"$ref_new": "version"}]` means: "only apply this write if the current stored version is less than the new version I'm writing."

**Insert-if-not-exists:**

```json
{
  "documents": [{"id": "doc-1", "attributes": {"content": "hello"}}],
  "condition": ["id", "Eq", null]
}
```

The condition `["id", "Eq", null]` evaluates to true only if the document doesn't exist yet.

**Conditional semantics:**
- Document exists + condition met → write applied
- Document exists + condition not met → write skipped (not an error), reflected in `rows_affected: 0`
- Document does not exist (for upsert) → write applied unconditionally
- Document does not exist (for patch/delete) → write skipped

### 8.6 Rate Limits and Backpressure

- **Global write throughput:** Unlimited
- **Per-namespace write rate:** 1 WAL commit/second (concurrent writes within the window are coalesced)
- **Max batch size:** 512 MB per request
- **Write latency:** p50 ~285ms (500KB batch), p90 ~370ms, p99 ~688ms
- **Backpressure:** When unindexed data exceeds 2 GB, bigRAG returns HTTP 429 with `Retry-After` header
- **Disable backpressure:** `X-BigRAG-Disable-Backpressure: true` header (use only for bulk imports)

---

## 9. Filter Engine

### 9.1 Filter DSL

Filters use a JSON array notation: `[field, operator, value]` for leaf conditions, and `["And"|"Or"|"Not", ...conditions]` for boolean combinations.

**Basic filter:**

```json
["category", "Eq", "ml"]
```

**Compound filter:**

```json
["And",
  ["category", "In", ["ml", "nlp"]],
  ["Or",
    ["score", "Gt", 4.0],
    ["featured", "Eq", true]
  ],
  ["Not",
    ["tags", "Contains", "deprecated"]
  ]
]
```

### 9.2 Filter Operators (Complete List)

#### Scalar Operators

| Operator | Types | Semantics |
|----------|-------|-----------|
| `Eq` | All | Equal |
| `NotEq` | All | Not equal |
| `Lt` | int, uint, float, datetime | Less than |
| `Lte` | int, uint, float, datetime | Less than or equal |
| `Gt` | int, uint, float, datetime | Greater than |
| `Gte` | int, uint, float, datetime | Greater than or equal |
| `In` | All scalar | Value in set |
| `NotIn` | All scalar | Value not in set |
| `Contains` | string | Substring match (case-sensitive) |
| `NotContains` | string | Substring not present |
| `Glob` | string | Glob pattern (`*`, `?`, `[...]`) |
| `NotGlob` | string | Glob pattern NOT matching |
| `IGlob` | string | Case-insensitive glob |
| `NotIGlob` | string | Case-insensitive glob NOT matching |
| `Regex` | string | PCRE regex match |
| `ContainsAllTokens` | string | All query tokens present (BM25-style) |
| `ContainsTokenSequence` | string | Query tokens appear in sequence (phrase match) |
| `ContainsAnyToken` | string | Any query token present |

#### Array Operators

| Operator | Types | Semantics |
|----------|-------|-----------|
| `Contains` | `[]T` | Array contains value |
| `NotContains` | `[]T` | Array does not contain value |
| `ContainsAny` | `[]T` | Array contains any of the values |
| `NotContainsAny` | `[]T` | Array contains none of the values |
| `ContainsAll` | `[]T` | Array contains all of the values |
| `AnyEq` | `[]T` | Any array element equals value |
| `AnyLt` | `[]int,uint,float,datetime` | Any element < value |
| `AnyLte` | `[]int,uint,float,datetime` | Any element ≤ value |
| `AnyGt` | `[]int,uint,float,datetime` | Any element > value |
| `AnyGte` | `[]int,uint,float,datetime` | Any element ≥ value |

#### Boolean Combinators

| Operator | Semantics |
|----------|-----------|
| `And` | All conditions must be true |
| `Or` | At least one condition must be true |
| `Not` | Condition must be false |

### 9.3 Filter Execution Strategy

bigRAG evaluates filters using a cost-based optimizer:

1. **Filter-first (pre-filter ANN):** For highly selective filters (estimated hit rate < 1%), bigRAG uses the attribute indexes to build a candidate document set first, then runs ANN search only within that set.
2. **ANN-first then filter (post-filter):** For low-selectivity filters, bigRAG runs ANN to get top-N candidates, then applies filters. N is oversampled (N = `top_k × oversample_factor`) to ensure `top_k` results survive filtering.
3. **Hybrid (filter + ANN interleaved):** For medium-selectivity filters, uses a combination.

**Filter-aware HNSW (v2 roadmap):** Pre-filtering is expensive if the filtered set is large. bigRAG v2 will implement HNSW with integrated filter awareness — the HNSW graph traversal natively skips nodes that don't satisfy the filter, achieving both high recall and efficient filtering simultaneously.

### 9.4 Null Handling

- `["field", "Eq", null]` — matches documents where `field` is explicitly null OR absent
- `["field", "NotEq", null]` — matches documents where `field` is present and not null
- Array operators on null arrays return false (null ≠ empty array)

---

## 10. Namespace Management

### 10.1 CRUD Operations

#### List Namespaces

`GET /v1/namespaces?prefix={prefix}&cursor={cursor}&page_size={n}`

```json
{
  "namespaces": [
    {"id": "tenant-abc", "doc_count": 125000},
    {"id": "tenant-def", "doc_count": 87000}
  ],
  "next_cursor": "eyJsYXN0IjoidGVuYW50LWRlZiJ9"
}
```

Parameters:
- `prefix`: Filter namespaces by name prefix
- `cursor`: Pagination cursor from previous response
- `page_size`: Results per page, default 100, max 1000

#### Get Namespace Metadata

`GET /v1/namespaces/{namespace}`

```json
{
  "id": "tenant-abc",
  "doc_count": 125000,
  "vector_count": 124850,
  "schema": {
    "vector": {"type": "[1536]f32", "distance_metric": "cosine_distance"},
    "title": {"type": "string", "filterable": true, "full_text_search": true},
    "score": {"type": "float", "filterable": true}
  },
  "index_state": {
    "ann": "ready",
    "fts": "building",
    "fts_progress": 0.73
  },
  "storage": {
    "logical_bytes": 1073741824,
    "physical_bytes": 524288000,
    "segments": 12
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-03-01T12:00:00Z"
}
```

The `index_state` field shows the current indexing status for each index type. `"building"` means the index is being constructed in the background; queries will still work but may use exhaustive search or partial indexes.

#### Delete Namespace

`DELETE /v1/namespaces/{namespace}`

Deletes all documents, indexes, and data in the namespace. Irreversible. Returns 204 No Content.

#### Copy Namespace

`POST /v1/namespaces/{destination}/copy`

```json
{
  "source_namespace": "prod-tenant-abc",
  "source_region": "aws-us-east-1",
  "encryption_key_id": "key-xyz"
}
```

Server-side copy: data is copied within the object store without passing through bigRAG's compute layer. Supports cross-region copy (within same cloud provider) and cross-organization copy.

### 10.2 Namespace Lifecycle

```
Created (implicit on first write)
    │
    ▼
Active (accepting reads + writes)
    │
    ├─── Idle (no traffic for inactivity_timeout)
    │        └── Cache evicted from DRAM/NVMe (data safe on object storage)
    │
    └─── Deleted (DELETE /v1/namespaces/{ns})
             └── Data removed from object storage after retention_period
```

**Inactivity cache eviction:** By default, namespaces not accessed in 1 hour have their NVMe cache evicted. The next query triggers a cold read (~200-500ms). Cache TTL is configurable per namespace:

```json
{
  "cache": {
    "inactivity_evict_after": "1h",
    "pin": false
  }
}
```

`"pin": true` keeps the namespace in NVMe cache indefinitely (use for hot namespaces).

### 10.3 Multi-Tenant Naming Conventions

For SaaS applications with per-tenant namespaces:

```
Pattern: {env}_{table}_{tenant_id}

Examples:
  prod_conversations_user-123
  prod_documents_org-abc
  staging_emails_user-456
```

**Why this matters:** The prefix `{env}_{table}_{tenant_id}` allows:
- List all namespaces for a given tenant: `prefix=prod_conversations_user-123`
- List all conversation namespaces: `prefix=prod_conversations_`
- Compliance delete (GDPR): find all namespaces matching `*_user-123`, delete them

---

## 11. Schema System

### 11.1 Schema Definition

Schemas are defined inline during first write (implicit schema evolution) or explicitly via the schema API.

**Explicit schema definition:**

`PUT /v1/namespaces/{namespace}/schema`

```json
{
  "schema": {
    "vector": {
      "type": "[1536]f32",
      "distance_metric": "cosine_distance",
      "ann": true
    },
    "title": {
      "type": "string",
      "filterable": true,
      "full_text_search": {
        "tokenizer": "word_v3",
        "language": "english",
        "stemming": false,
        "remove_stopwords": false,
        "ascii_folding": false,
        "k1": 1.2,
        "b": 0.75
      }
    },
    "content": {
      "type": "string",
      "filterable": false,
      "full_text_search": true
    },
    "category": {
      "type": "string",
      "filterable": true
    },
    "tags": {
      "type": "[]string",
      "filterable": true
    },
    "score": {
      "type": "float",
      "filterable": true
    },
    "published_at": {
      "type": "datetime",
      "filterable": true
    },
    "metadata": {
      "type": "string",
      "filterable": false
    }
  }
}
```

### 11.2 Implicit Schema Inference

If no schema is defined, bigRAG infers schema from the first write:
- `string` values → `string` type, `filterable: true`
- `integer` values → `int` type, `filterable: true`
- `float` values → `float` type, `filterable: true`
- `boolean` values → `bool` type, `filterable: true`
- `array` values → inferred array type, `filterable: true`
- String values matching ISO 8601 → `datetime` type

Subsequent writes must conform to the inferred schema. Type mismatches return HTTP 422 Unprocessable Entity.

### 11.3 Online Schema Updates

The following changes are safe to apply online:

| Change | Impact | Notes |
|--------|--------|-------|
| Add `filterable: true` to non-filterable attribute | Background index build | Queries return HTTP 202 until ready |
| Add `full_text_search: true` | Background FTS build | BM25 queries return HTTP 202 until ready |
| Change FTS parameters (k1, b, stemming...) | Background FTS rebuild | Old index used until rebuild completes |
| Remove `filterable` from filterable attribute | Immediate index drop | Queries on this attribute return error |
| Add new attribute | Immediate | New attribute accepted in writes |

The following changes are **NOT** supported online:
- Changing vector dimension
- Changing distance metric
- Changing attribute type (string → int, etc.)
- Removing an attribute (stop writing it; data remains queryable)

For breaking changes: export namespace → create new namespace with new schema → re-import.

### 11.4 Multiple Vector Columns

bigRAG supports multiple vector columns per document (in beta in turbopuffer as of February 2026):

```json
{
  "schema": {
    "title_vector": {
      "type": "[384]f32",
      "distance_metric": "cosine_distance",
      "ann": true
    },
    "content_vector": {
      "type": "[1536]f32",
      "distance_metric": "cosine_distance",
      "ann": true
    }
  }
}
```

Documents with multiple vectors can be searched on either column:

```json
{"rank_by": ["title_vector", "ANN", [...]]}
{"rank_by": ["content_vector", "ANN", [...]]}
```

**Use case:** Title and content have different embedding dimensions/models; search on either independently or fuse them in a hybrid query.

---

## 12. REST API Specification

### 12.1 Base URL and Versioning

```
{host}/v1/                 # Current stable API
{host}/v2/                 # Next version (when applicable)
```

For self-hosted bigRAG: `http://localhost:8080/v1/`

### 12.2 Authentication

All requests must include an API key:

```
Authorization: Bearer {api_key}
```

Or as query parameter (not recommended for production):

```
?api_key={api_key}
```

### 12.3 Endpoints Reference

#### Namespaces

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/namespaces` | List namespaces (paginated) |
| GET | `/v1/namespaces/{ns}` | Get namespace metadata |
| DELETE | `/v1/namespaces/{ns}` | Delete namespace |
| POST | `/v1/namespaces/{ns}/copy` | Copy namespace |
| GET | `/v1/namespaces/{ns}/recall` | Check ANN recall |
| GET | `/v1/namespaces/{ns}/schema` | Get schema |
| PUT | `/v1/namespaces/{ns}/schema` | Update schema |
| GET | `/v1/namespaces/{ns}/stats` | Get detailed stats |

#### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/namespaces/{ns}/documents` | Upsert documents |
| POST | `/v1/namespaces/{ns}/query` | Query documents |
| GET | `/v1/namespaces/{ns}/documents/{id}` | Get single document by ID |
| DELETE | `/v1/namespaces/{ns}/documents` | Delete documents by ID array |

#### Administration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health` | Health check |
| GET | `/v1/metrics` | Prometheus metrics |
| GET | `/v1/admin/namespaces` | Admin: list all namespaces with stats |
| POST | `/v1/admin/compact/{ns}` | Trigger manual compaction |
| POST | `/v1/admin/warm/{ns}` | Pre-warm namespace into cache |
| GET | `/v1/admin/config` | Get current runtime config |

### 12.4 Error Format

All errors return JSON with the following structure:

```json
{
  "error": {
    "code": "NAMESPACE_NOT_FOUND",
    "message": "Namespace 'tenant-xyz' does not exist",
    "details": {
      "namespace": "tenant-xyz"
    },
    "request_id": "req_01ABC123"
  }
}
```

**Error codes:**

| HTTP Status | Error Code | Description |
|------------|-----------|-------------|
| 400 | `INVALID_REQUEST` | Malformed JSON or invalid parameters |
| 400 | `SCHEMA_MISMATCH` | Document attributes don't match schema |
| 400 | `INVALID_FILTER` | Filter syntax error |
| 400 | `DIMENSION_MISMATCH` | Vector dimension doesn't match namespace |
| 401 | `UNAUTHORIZED` | Missing or invalid API key |
| 403 | `FORBIDDEN` | API key doesn't have permission |
| 404 | `NAMESPACE_NOT_FOUND` | Namespace doesn't exist |
| 404 | `DOCUMENT_NOT_FOUND` | Document ID not found |
| 409 | `SCHEMA_CONFLICT` | Schema change incompatible with existing data |
| 422 | `UNPROCESSABLE` | Valid JSON but semantically invalid |
| 429 | `RATE_LIMITED` | Write backpressure: too much unindexed data |
| 202 | `INDEX_BUILDING` | Query succeeded but index still building |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Temporary unavailability |

### 12.5 Request/Response Headers

**Request headers:**

| Header | Description |
|--------|-------------|
| `Authorization` | `Bearer {api_key}` |
| `Content-Type` | `application/json` |
| `X-BigRAG-Disable-Backpressure` | `true` to disable 429 backpressure (bulk import) |
| `X-BigRAG-Consistency` | `strong` (default) or `eventual` |
| `X-Request-ID` | Client-provided request ID for tracing |

**Response headers:**

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Echoed from request or server-generated |
| `X-BigRAG-Version` | Server version |
| `X-BigRAG-Region` | Serving region |
| `Retry-After` | On 429: seconds to wait before retry |

---

## 13. Authentication & Authorization

### 13.1 API Key Model

bigRAG uses API keys for authentication. Keys are scoped and have the following properties:

```json
{
  "id": "key_01ABC123",
  "name": "Production Write Key",
  "prefix": "br_",
  "created_at": "2024-01-01T00:00:00Z",
  "last_used_at": "2024-03-01T12:00:00Z",
  "permissions": {
    "namespaces": ["tenant-*"],
    "operations": ["read", "write", "delete"],
    "admin": false
  },
  "expiry": null
}
```

**Permission scopes:**

| Scope | Description |
|-------|-------------|
| `read` | Query documents, get namespace metadata |
| `write` | Upsert, patch documents |
| `delete` | Delete documents, delete namespace |
| `schema` | Modify namespace schema |
| `admin` | Full access including listing all namespaces, metrics |

**Namespace restrictions:**
- `"namespaces": ["*"]` — access all namespaces
- `"namespaces": ["tenant-abc"]` — access only namespace `tenant-abc`
- `"namespaces": ["tenant-*"]` — glob pattern, access all `tenant-` prefixed namespaces

This enables **multi-tenant key isolation**: each tenant gets a key that can only access their own namespaces.

### 13.2 JWT Authentication (Optional)

For integrations with existing identity providers, bigRAG supports JWT Bearer tokens:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiJ9...
```

Configure JWT validation in `bigrag.toml`:

```toml
[auth.jwt]
issuer = "https://auth.example.com"
audience = "bigrag"
jwks_uri = "https://auth.example.com/.well-known/jwks.json"
namespace_claim = "bigrag_namespaces"  # JWT claim → namespace permissions
```

### 13.3 API Key Management Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/admin/api-keys` | Create API key |
| GET | `/v1/admin/api-keys` | List API keys |
| GET | `/v1/admin/api-keys/{id}` | Get API key details |
| DELETE | `/v1/admin/api-keys/{id}` | Revoke API key |
| PATCH | `/v1/admin/api-keys/{id}` | Update permissions |

---

## 14. Multi-Tenancy Architecture

### 14.1 Namespace Isolation

Each namespace is an independent unit:
- Separate object storage prefix
- Separate ANN index
- Separate BM25 inverted index
- Separate compaction lifecycle
- Separate cache quota (configurable)

**Namespace limits (defaults, all configurable):**

| Limit | Default | Max |
|-------|---------|-----|
| Documents per namespace | 500M | Unlimited (with sharding) |
| Vector dimensions | 10,752 | 65,536 |
| Attributes per namespace | 256 | 1024 |
| Attribute name length | 128 bytes | 512 bytes |
| Document size | 64 MiB | 256 MiB |
| ID size | 64 bytes | 256 bytes |
| Query result limit | 10,000 | 100,000 |
| Aggregation groups | 10,000 | 100,000 |

### 14.2 Tenant Isolation Models

#### Shared Namespace Cluster (Default)
All tenants share compute and NVMe cache. Data is logically isolated by namespace. Suitable for most SaaS applications.

```
bigRAG cluster
├── tenant-001 namespace (own S3 prefix)
├── tenant-002 namespace (own S3 prefix)
└── tenant-N namespace (own S3 prefix)
```

#### Dedicated Namespace Cache
High-value tenants can have their namespaces pinned in NVMe/DRAM:

```json
{"cache": {"pin": true, "tier": "nvme"}}
```

#### Separate bigRAG Instance
For complete isolation, deploy a separate bigRAG instance per tenant (recommended for enterprise tenants with compliance requirements):

```yaml
# docker-compose.yml
services:
  bigrag-tenant-enterprise:
    image: bigrag/bigrag:latest
    environment:
      BIGRAG_STORAGE_BUCKET: my-bucket/enterprise-tenant
      BIGRAG_AUTH_KEYS: "br_enterprise_key_123"
```

### 14.3 Document-Level Access Control

bigRAG supports document-level access control via namespace-level filter rules:

```json
{
  "access_control": {
    "filter": ["owner_id", "Eq", "{api_key.metadata.user_id}"]
  }
}
```

This filter is automatically AND-ed with every query for that API key. The `{api_key.metadata.user_id}` template is substituted with the value from the API key's metadata at query time.

---

## 15. Client SDKs

### 15.1 Official SDKs

bigRAG ships first-class SDKs for the most common languages:

| Language | Package | Status |
|----------|---------|--------|
| Python | `pip install bigrag` | v1.0 |
| TypeScript/Node | `npm install @bigrag/client` | v1.0 |
| Go | `go get github.com/bigrag-io/bigrag-go` | v1.0 |
| Rust | `cargo add bigrag` | v1.0 (reference impl) |
| Java/Kotlin | Maven: `io.bigrag:bigrag-java` | v1.0 |
| Ruby | `gem install bigrag` | v1.0 |

### 15.2 Python SDK Design

```python
from bigrag import BigRAG, Namespace, Document

# Initialize client
client = BigRAG(
    api_key="br_your_key",
    base_url="http://localhost:8080",  # or https://your-bigrag.cloud
    timeout=30.0,
    max_retries=3,
    region="aws-us-east-1"
)

# Namespace operations
ns = client.namespace("tenant-abc")

# Upsert documents
ns.upsert([
    Document(
        id="doc-1",
        vector=[0.1, 0.2, 0.3],
        attributes={"title": "Hello world", "score": 4.5}
    )
])

# Query: vector ANN
results = ns.query(
    rank_by=("vector", "ANN", [0.1, 0.2, 0.3]),
    filters=["score", "Gt", 4.0],
    limit=10,
    include_attributes=["title", "score"]
)

# Query: BM25 full-text search
results = ns.query(
    rank_by=("content", "BM25", "retrieval augmented generation"),
    limit=10
)

# Hybrid search
results = ns.query(
    queries=[
        {"rank_by": ("vector", "ANN", [0.1, 0.2, ...]), "limit": 100},
        {"rank_by": ("content", "BM25", "rag overview"), "limit": 100},
    ],
    fusion={"method": "rrf", "k": 60},
    limit=10
)

# Async client
from bigrag import AsyncBigRAG
async_client = AsyncBigRAG(api_key="br_...", base_url="...")
```

### 15.3 TypeScript SDK Design

```typescript
import { BigRAG } from '@bigrag/client';

const client = new BigRAG({
  apiKey: 'br_your_key',
  baseUrl: 'http://localhost:8080',
  timeout: 30000,
  maxRetries: 3
});

const ns = client.namespace('tenant-abc');

// Upsert
await ns.upsert([
  { id: 'doc-1', vector: [0.1, 0.2, 0.3], attributes: { title: 'Hello' } }
]);

// Query
const results = await ns.query({
  rankBy: ['vector', 'ANN', [0.1, 0.2, 0.3]],
  filters: ['score', 'Gt', 4.0],
  limit: { total: 10 },
  includeAttributes: ['title', 'score']
});

// Async iteration over large result sets
for await (const ns of client.namespaces({ prefix: 'tenant-' })) {
  console.log(ns.id, ns.doc_count);
}
```

### 15.4 LangChain Integration

bigRAG ships a first-class LangChain vectorstore adapter:

```python
from bigrag.integrations.langchain import BigRAGVectorStore
from langchain.embeddings import OpenAIEmbeddings

vectorstore = BigRAGVectorStore(
    namespace="my-documents",
    embedding=OpenAIEmbeddings(),
    bigrag_client=BigRAG(api_key="br_...", base_url="..."),
    text_key="content",
    metadata_keys=["source", "page_number"]
)

# Add documents
vectorstore.add_texts(
    texts=["LangChain is a framework for LLM applications"],
    metadatas=[{"source": "docs", "page_number": 1}]
)

# Similarity search
docs = vectorstore.similarity_search("LLM framework", k=5)

# Hybrid search (bigRAG extension)
docs = vectorstore.similarity_search(
    "LLM framework",
    k=5,
    search_type="hybrid",
    hybrid_alpha=0.5
)

# As retriever (for RAG chains)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
```

### 15.5 LlamaIndex Integration

```python
from bigrag.integrations.llamaindex import BigRAGVectorStore
from llama_index.core import VectorStoreIndex

vector_store = BigRAGVectorStore(
    namespace="my-index",
    bigrag_url="http://localhost:8080",
    api_key="br_..."
)

index = VectorStoreIndex.from_vector_store(vector_store)
retriever = index.as_retriever(similarity_top_k=5)
```

### 15.6 OpenAI Embeddings Integration

bigRAG does NOT generate embeddings internally (this is intentional — embedding models evolve rapidly and are best handled by the application layer). However, bigRAG provides an optional sidecar embedding server:

```yaml
# docker-compose.yml
services:
  bigrag:
    image: bigrag/bigrag:latest

  embeddings:
    image: bigrag/embeddings:latest  # optional sidecar
    environment:
      MODEL: "nomic-ai/nomic-embed-text-v1.5"  # runs via Candle/ONNX
      OPENAI_COMPATIBLE_API: "true"
```

The embedding sidecar exposes an OpenAI-compatible `/v1/embeddings` endpoint, allowing any OpenAI-compatible client to generate embeddings locally.

---

## 16. Self-Hosted Deployment — Docker

### 16.1 Quick Start

```bash
# Minimal local deployment (local filesystem storage)
docker run -d \
  --name bigrag \
  -p 8080:8080 \
  -v $(pwd)/data:/data \
  -e BIGRAG_STORAGE_BACKEND=local \
  -e BIGRAG_STORAGE_PATH=/data \
  -e BIGRAG_AUTH_MASTER_KEY=br_dev_key \
  bigrag/bigrag:latest

# Test it
curl -X POST http://localhost:8080/v1/namespaces/test/documents \
  -H "Authorization: Bearer br_dev_key" \
  -H "Content-Type: application/json" \
  -d '{"documents": [{"id": "1", "vector": [0.1, 0.2, 0.3], "attributes": {"text": "hello"}}]}'
```

### 16.2 Docker Compose (Recommended for Development)

```yaml
# docker-compose.yml
version: "3.9"

services:
  bigrag:
    image: bigrag/bigrag:latest
    container_name: bigrag
    restart: unless-stopped
    ports:
      - "8080:8080"
      - "9090:9090"  # Prometheus metrics
    volumes:
      - bigrag_data:/data
      - ./bigrag.toml:/etc/bigrag/config.toml:ro
    environment:
      BIGRAG_CONFIG: /etc/bigrag/config.toml
      BIGRAG_LOG_LEVEL: info
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Optional: MinIO for S3-compatible local object storage
  minio:
    image: minio/minio:latest
    container_name: bigrag-minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"  # MinIO console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data

  # Optional: BigRAG Admin UI
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

### 16.3 Docker Compose with S3

```yaml
# docker-compose.s3.yml
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
      - /nvme/bigrag:/nvme  # mount NVMe for L2 cache
    ports:
      - "8080:8080"
```

### 16.4 Single Binary Mode

bigRAG ships as a single statically-linked binary (no runtime dependencies):

```bash
# Download
curl -L https://github.com/bigrag-io/bigrag/releases/latest/download/bigrag-linux-amd64 -o bigrag
chmod +x bigrag

# Run
./bigrag server \
  --storage-backend s3 \
  --storage-bucket my-bucket \
  --storage-region us-east-1 \
  --auth-key br_my_key \
  --port 8080 \
  --cache-path /tmp/bigrag-cache \
  --cache-size 10gb
```

### 16.5 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_STORAGE_BACKEND` | `s3`, `gcs`, `azureblob`, `minio`, `local` | `local` |
| `BIGRAG_STORAGE_BUCKET` | Bucket name (or path for local) | `bigrag-data` |
| `BIGRAG_STORAGE_REGION` | Cloud region | `us-east-1` |
| `BIGRAG_STORAGE_ENDPOINT` | Custom endpoint (MinIO, Ceph) | — |
| `BIGRAG_STORAGE_PREFIX` | Object key prefix | `bigrag/` |
| `BIGRAG_CACHE_DRAM_SIZE` | L1 DRAM cache size | `20%` of RAM |
| `BIGRAG_CACHE_NVME_PATH` | L2 NVMe cache directory | `/tmp/bigrag-nvme` |
| `BIGRAG_CACHE_NVME_SIZE` | L2 NVMe cache max size | `all available` |
| `BIGRAG_AUTH_MASTER_KEY` | Master API key (create new keys via API) | — |
| `BIGRAG_AUTH_DISABLE` | Disable auth (dev only) | `false` |
| `BIGRAG_LOG_LEVEL` | `debug`, `info`, `warn`, `error` | `info` |
| `BIGRAG_LOG_FORMAT` | `json`, `text` | `json` |
| `BIGRAG_PORT` | HTTP server port | `8080` |
| `BIGRAG_METRICS_PORT` | Prometheus metrics port | `9090` |
| `BIGRAG_MAX_NAMESPACES` | Max namespaces (0 = unlimited) | `0` |
| `BIGRAG_COMPACTION_WORKERS` | Background compaction threads | `2` |
| `BIGRAG_WRITE_WORKERS` | WAL writer threads | `4` |
| `BIGRAG_QUERY_WORKERS` | Query handler threads | `num_cpus` |
| `BIGRAG_TLS_CERT` | Path to TLS certificate | — |
| `BIGRAG_TLS_KEY` | Path to TLS private key | — |

---

## 17. Kubernetes Deployment

### 17.1 Architecture on Kubernetes

```
┌─────────────────────────────────────────────┐
│              Kubernetes Cluster              │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │        bigrag-query Deployment      │    │
│  │  HPA: 2-20 replicas (CPU/RPS based) │    │
│  │  Resource: 4 CPU, 16Gi RAM, NVMe    │    │
│  │  Anti-affinity: spread across zones │    │
│  └──────────────┬──────────────────────┘    │
│                 │                            │
│  ┌──────────────▼──────────────────────┐    │
│  │        bigrag-write Deployment      │    │
│  │  HPA: 2-10 replicas                 │    │
│  │  Resource: 2 CPU, 8Gi RAM           │    │
│  └──────────────┬──────────────────────┘    │
│                 │                            │
│  ┌──────────────▼──────────────────────┐    │
│  │    bigrag-compactor StatefulSet     │    │
│  │  1-3 replicas (distributed lock)   │    │
│  │  Resource: 4 CPU, 8Gi RAM           │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  External: AWS S3 / GCS / Azure Blob        │
└─────────────────────────────────────────────┘
```

### 17.2 Helm Chart

bigRAG ships an official Helm chart:

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

### 17.3 Helm Values

```yaml
# values.yaml
image:
  repository: bigrag/bigrag
  tag: latest
  pullPolicy: IfNotPresent

storage:
  backend: s3          # s3 | gcs | azureblob | minio | local
  bucket: bigrag
  region: us-east-1
  prefix: bigrag/
  # For MinIO or custom S3 endpoints:
  endpoint: ""
  credentials:
    existingSecret: aws-credentials  # k8s secret with AWS_ACCESS_KEY_ID etc.

auth:
  masterKey: ""         # use k8s secret instead
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
    requests:
      cpu: 2
      memory: 8Gi
    limits:
      cpu: 4
      memory: 16Gi

write:
  replicas: 2
  resources:
    requests:
      cpu: 1
      memory: 4Gi

compactor:
  replicas: 2
  resources:
    requests:
      cpu: 2
      memory: 4Gi

cache:
  dram:
    size: "20%"
  nvme:
    enabled: false
    storageClass: "fast-nvme"
    size: 500Gi
    mountPath: /nvme

metrics:
  enabled: true
  serviceMonitor: true  # for Prometheus Operator

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

---

## 18. Configuration Reference

### 18.1 bigrag.toml

```toml
[server]
host = "0.0.0.0"
port = 8080
metrics_port = 9090
max_connections = 10000
request_timeout_ms = 60000
max_request_body_mb = 512

[storage]
backend = "s3"          # s3 | gcs | azureblob | minio | local
bucket = "bigrag-prod"
region = "us-east-1"
prefix = "bigrag/"
endpoint = ""           # custom endpoint for MinIO/Ceph
# Uncomment for Azure:
# account_name = ""
# account_key = ""
# For GCS, use Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS

[cache]
# L1: DRAM
dram_max_bytes = 0        # 0 = 20% of available RAM
dram_eviction = "lru"     # lru | lfu | arc

# L2: NVMe
nvme_path = "/var/cache/bigrag"
nvme_max_bytes = 0        # 0 = use all available disk
nvme_eviction = "lru"

# Namespace cache TTL
namespace_inactivity_evict_secs = 3600  # 1 hour
hot_namespace_pin = []    # ["tenant-abc", "tenant-def"] to always keep hot

[indexing]
# ANN
ann_algorithm = "spfresh"  # spfresh | hnsw
ann_default_recall_target = 0.90
ann_nprobe_factor = 1.0   # multiply nprobe by this for higher recall
hnsw_m = 16
hnsw_ef_construction = 200
hnsw_ef_search = 64

# Vector quantization
default_vector_type = "f32"  # f32 | f16 | int8 | binary

# FTS
fts_ram_budget_mb = 1024  # BM25 index RAM budget

# Compaction
l0_merge_threshold = 4     # merge L0 when count exceeds this
l1_max_segment_mb = 512
l2_max_segment_mb = 2048
compaction_workers = 2
compaction_cpu_budget = 0.5  # fraction of CPU for compaction

[auth]
master_key = ""           # set via env: BIGRAG_AUTH_MASTER_KEY
disable = false           # never disable in production

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
log_level = "info"        # debug | info | warn | error
log_format = "json"       # json | text
slow_query_threshold_ms = 100
enable_query_log = false  # log all queries (verbose)
metrics_prefix = "bigrag" # Prometheus metrics prefix

[tls]
enabled = false
cert_file = ""
key_file = ""
ca_file = ""              # for mTLS
```

---

## 19. Observability & Metrics

### 19.1 Health Checks

`GET /v1/health`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "storage": {"status": "ok", "backend": "s3"},
  "cache": {
    "dram_used_bytes": 2147483648,
    "dram_max_bytes": 4294967296,
    "nvme_used_bytes": 10737418240,
    "nvme_max_bytes": 107374182400
  },
  "namespaces_loaded": 1247
}
```

`GET /v1/health/ready` — Kubernetes readiness probe
`GET /v1/health/live` — Kubernetes liveness probe

### 19.2 Prometheus Metrics

**Core metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `bigrag_queries_total` | Counter | Total queries, labeled by namespace, status |
| `bigrag_query_duration_ms` | Histogram | Query latency histogram |
| `bigrag_writes_total` | Counter | Total write operations |
| `bigrag_write_duration_ms` | Histogram | Write latency histogram |
| `bigrag_documents_total` | Gauge | Total documents per namespace |
| `bigrag_storage_bytes` | Gauge | Storage used per namespace |
| `bigrag_cache_hits_total` | Counter | Cache hits by tier (dram/nvme/cold) |
| `bigrag_cache_misses_total` | Counter | Cache misses by tier |
| `bigrag_ann_recall` | Gauge | Estimated ANN recall per namespace |
| `bigrag_fts_queries_total` | Counter | BM25 query count |
| `bigrag_compaction_runs_total` | Counter | Compaction job count |
| `bigrag_compaction_duration_ms` | Histogram | Compaction duration |
| `bigrag_index_build_duration_ms` | Histogram | Index build latency |
| `bigrag_wal_segments_total` | Gauge | Uncompacted WAL segments per namespace |
| `bigrag_object_store_requests_total` | Counter | Object store requests by operation |
| `bigrag_object_store_latency_ms` | Histogram | Object store request latency |

### 19.3 Structured Logging

All log lines are JSON (configurable to text):

```json
{
  "ts": "2024-03-01T12:00:00.123Z",
  "level": "info",
  "msg": "query completed",
  "request_id": "req_01ABC123",
  "namespace": "tenant-abc",
  "query_type": "ann",
  "docs_scanned": 125000,
  "docs_returned": 10,
  "duration_ms": 8,
  "cache_tier": "nvme",
  "recall_estimate": 0.94
}
```

### 19.4 Admin Dashboard

bigRAG ships a built-in web admin dashboard (available at `:3000` or configurable path):

**Dashboard features:**
- Real-time namespace list with doc counts and storage
- Query/write rate graphs per namespace
- Cache utilization (DRAM/NVMe)
- ANN recall monitoring per namespace
- Index build status
- Slow query log
- Admin operations: compact, warm, delete namespace
- Schema browser
- Interactive query explorer (run queries via UI)

The dashboard is built with Next.js and shadcn/ui, served as static assets bundled into the main bigRAG binary.

---

## 20. Performance Targets & Benchmarks

### 20.1 Latency Targets

| Scenario | p50 | p90 | p99 |
|----------|-----|-----|-----|
| ANN query, warm (NVMe cached) | 8ms | 15ms | 35ms |
| ANN query, hot (DRAM cached) | <1ms | 3ms | 8ms |
| ANN query, cold (object store) | 150ms | 300ms | 500ms |
| BM25 query, warm | 5ms | 20ms | 50ms |
| Hybrid query (ANN+BM25), warm | 12ms | 25ms | 60ms |
| Upsert (500KB batch) | 285ms | 370ms | 688ms |
| Delete by ID (100 docs) | 20ms | 40ms | 100ms |

### 20.2 Throughput Targets

| Metric | Target |
|--------|--------|
| Queries (per node, 8-core) | 1,000+ QPS |
| Writes (per namespace) | 10,000 docs/s at 32 MB/s |
| Namespaces (per cluster) | 10M+ |
| Documents (per namespace) | 500M+ |
| Total documents (cluster) | Trillions |

### 20.3 Scale Targets

| Dimension | Target |
|-----------|--------|
| Vector dimensions | Up to 10,752 (f32) |
| Vector dimensions (f16) | Up to 65,536 |
| Index build speed | 1M vectors/minute (f32, 768 dims) |
| Compaction throughput | 500MB/min per worker |
| Cold read throughput | Limited by object store (S3: ~5Gb/s per prefix) |

### 20.4 ANN Recall Characteristics

Based on SPFresh benchmarks at 100B vectors (1,024 dims, f16):
- p50 latency: ~40ms, p99: ~200ms
- QPS: 1,000+
- Recall: 92% at default settings

Recall can be tuned:

| Configuration | Recall | Latency impact |
|--------------|--------|---------------|
| `recall_target: 0.85` | ~85% | -30% latency |
| `recall_target: 0.90` | ~90% | baseline |
| `recall_target: 0.95` | ~95% | +50% latency |
| `recall_target: 1.00` | 100% | kNN (requires filter) |

---

## 21. Security Model

### 21.1 Encryption

| Layer | Algorithm | Notes |
|-------|-----------|-------|
| In transit | TLS 1.3 | Client ↔ bigRAG, bigRAG ↔ object store |
| At rest | AES-256-GCM | Handled by object store (S3 SSE, GCS CMEK) |
| Application-level | Optional CMEK | Customer-managed keys via KMS (AWS KMS, GCP KMS, HashiCorp Vault) |
| API keys | Bcrypt (stored hash) | Keys never stored in plain text |

### 21.2 Network Security

- **Private endpoint support:** Configure bigRAG to listen on a private IP only
- **VPC/VNet integration:** Deploy in private subnets, no public IP required
- **Firewall rules:** bigRAG respects standard TCP firewall rules; only the API port (8080) and metrics port (9090) need to be open
- **TLS client certificates (mTLS):** Optional, for service-to-service auth

### 21.3 Data Residency

bigRAG writes data to the object store bucket you configure. Data never leaves your chosen bucket/region unless you explicitly trigger a cross-region copy. This enables:
- EU data residency (deploy in AWS eu-central-1 with an eu-central-1 bucket)
- Air-gapped deployments (use MinIO on-prem)
- Sovereign cloud deployments (Azure Government, AWS GovCloud)

### 21.4 Compliance Readiness

| Standard | Self-Hosted Status | Notes |
|---------|-------------------|-------|
| SOC 2 | Infrastructure responsibility | bigRAG provides audit logs + access control; SOC2 audit is on the operator |
| GDPR | Supported | Namespace-per-user pattern + delete-by-filter enables right-to-erasure |
| HIPAA | Supported (with TLS + encryption) | Operator must complete BAA with cloud provider |
| FedRAMP | Possible (with GovCloud) | Requires additional hardening |
| ISO 27001 | Infrastructure responsibility | — |

### 21.5 Audit Logging

Every API operation is logged with:
- Timestamp
- API key ID (not the key itself)
- Operation type
- Namespace
- Document IDs affected (optional, for compliance)
- Source IP
- Request ID

Audit logs can be streamed to: S3, Elasticsearch, Splunk, or a webhook.

---

## 22. Backup & Recovery

### 22.1 Object Storage as Native Backup

Because bigRAG's primary state is object storage, **every write is already backed up** to the object store. The object store's own durability (99.999999999% for AWS S3) provides the primary durability guarantee.

For additional protection:

### 22.2 Namespace Copy (Cross-Region Backup)

```bash
# Copy namespace to backup region
curl -X POST https://api.bigrag.example.com/v1/namespaces/prod-tenant-abc/copy \
  -H "Authorization: Bearer br_admin_key" \
  -d '{
    "source_namespace": "prod-tenant-abc",
    "destination_namespace": "backup-tenant-abc",
    "destination_region": "eu-central-1",
    "destination_bucket": "bigrag-backup-eu"
  }'
```

- Entirely server-side (zero client bandwidth)
- Billed at 75% discount on standard write costs
- Supported within same cloud provider
- CMEK key must be available in destination region

### 22.3 Namespace Export

Export a namespace to Parquet or newline-delimited JSON:

```bash
curl -X POST https://api.bigrag.example.com/v1/namespaces/prod-tenant-abc/export \
  -H "Authorization: Bearer br_admin_key" \
  -d '{
    "format": "parquet",
    "destination": "s3://my-exports/tenant-abc-20240301.parquet",
    "include_vectors": true,
    "include_attributes": ["title", "score", "category"]
  }'
```

### 22.4 Scheduled Backups

bigRAG supports built-in scheduled backup jobs:

```toml
[backup]
enabled = true
schedule = "0 2 * * *"  # daily at 2am UTC
retain_days = 7
destination_bucket = "bigrag-backups"
destination_region = "eu-central-1"
namespace_filter = "prod-*"
```

### 22.5 Point-in-Time Recovery

WAL segments on object storage provide point-in-time recovery capability:

```bash
# Restore namespace to state at a specific timestamp
curl -X POST https://api.bigrag.example.com/v1/namespaces/restored-tenant/restore \
  -H "Authorization: Bearer br_admin_key" \
  -d '{
    "source_namespace": "prod-tenant-abc",
    "restore_to_timestamp": "2024-03-01T10:00:00Z"
  }'
```

WAL segments are retained for `wal_retention_days` (default: 7) before being garbage collected.

---

## 23. Migration & Import Tools

### 23.1 Migration from turbopuffer

bigRAG ships a migration tool that provides a drop-in API compatibility layer:

```bash
# Install migration tool
pip install bigrag-migrate

# Migrate namespace from turbopuffer to bigRAG
bigrag-migrate \
  --source turbopuffer \
  --source-api-key tpuf_key \
  --source-namespace my-namespace \
  --dest bigrag \
  --dest-url http://localhost:8080 \
  --dest-api-key br_key \
  --dest-namespace my-namespace \
  --batch-size 10000
```

### 23.2 API Compatibility Mode

bigRAG can run in turbopuffer compatibility mode, accepting turbopuffer's exact API format:

```toml
[compat]
turbopuffer = true  # accept turbopuffer API format at /v2/ endpoints
```

This allows switching turbopuffer clients to bigRAG by only changing the base URL:

```python
# Before (turbopuffer):
import turbopuffer as tpuf
tpuf.api_key = "tpuf_..."
ns = tpuf.Namespace("my-ns")

# After (bigRAG, zero code change needed in compat mode):
import turbopuffer as tpuf
tpuf.api_key = "br_..."
tpuf.api_base = "http://localhost:8080/v2"  # only change
ns = tpuf.Namespace("my-ns")  # all existing code works unchanged
```

### 23.3 Import from Other Vector DBs

| Source | Tool | Notes |
|--------|------|-------|
| Pinecone | `bigrag-migrate --source pinecone` | Requires Pinecone API key |
| Qdrant | `bigrag-migrate --source qdrant` | Qdrant collections → bigRAG namespaces |
| Weaviate | `bigrag-migrate --source weaviate` | Weaviate classes → bigRAG namespaces |
| Milvus | `bigrag-migrate --source milvus` | Milvus collections → bigRAG namespaces |
| pgvector | `bigrag-migrate --source pgvector` | Postgres connection string required |
| Chroma | `bigrag-migrate --source chroma` | Chroma collections → bigRAG namespaces |
| Parquet | `bigrag-migrate --source parquet` | Import from exported Parquet files |
| JSONL | `bigrag-migrate --source jsonl` | Import from newline-delimited JSON |

---

## 24. Testing Strategy

### 24.1 Unit Tests (Rust)

Core engine components must have ≥80% unit test coverage:

- **Filter engine:** Every operator tested with positive/negative cases, null handling, type mismatches
- **BM25 scorer:** Known query/doc pairs with expected scores, tokenization edge cases
- **WAL serialization:** Round-trip write→read for every document type
- **BSF encoder/decoder:** Round-trip for every column type, compression codec
- **SPFresh index:** Recall ≥ 90% on synthetic 100K vector dataset
- **HNSW index:** Recall ≥ 99% on synthetic 100K vector dataset

### 24.2 Integration Tests

Integration tests run against a real bigRAG instance (local or CI):

```rust
#[tokio::test]
async fn test_upsert_and_query() {
    let ns = test_namespace().await;  // creates random namespace
    defer! { ns.delete().await; }     // cleanup on test exit

    ns.upsert(vec![
        doc("1", vec![0.1, 0.2, 0.3], attrs! {"title" => "hello"}),
    ]).await.unwrap();

    let results = ns.query(ann_query([0.1, 0.2, 0.3], 5)).await.unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].id, "1");
}
```

Test patterns:
- **Per-test namespace with random name** — never conflicts between parallel tests
- **Cleanup in test teardown** — `delete_namespace()` in `defer!` block
- **CI-safe** — run against local bigRAG instance in Docker (no external dependencies)

### 24.3 Benchmark Suite

bigRAG ships a `bench` binary for performance measurement:

```bash
# ANN recall benchmark (100K vectors, 768 dims, cosine)
bigrag-bench ann \
  --dims 768 \
  --count 100000 \
  --metric cosine_distance \
  --top-k 10 \
  --nqueries 1000 \
  --recall-target 0.90

# Write throughput benchmark
bigrag-bench write \
  --batch-size 10000 \
  --total 1000000 \
  --dims 768

# Query throughput benchmark (warm cache)
bigrag-bench query-throughput \
  --concurrency 16 \
  --duration 60s
```

### 24.4 Compatibility Testing

A compatibility test suite validates bigRAG's compatibility with the turbopuffer API:

```bash
# Run against real turbopuffer (requires TURBOPUFFER_API_KEY)
bigrag-compat-test --backend turbopuffer

# Run against bigRAG
bigrag-compat-test --backend bigrag --url http://localhost:8080 --api-key br_key

# Diff the outputs
bigrag-compat-test --diff --backend-a turbopuffer --backend-b bigrag
```

---

## 25. Open Source Governance & Community

### 25.1 License

**Apache License 2.0** — permissive, enterprise-friendly. You can:
- Use bigRAG in commercial products without open-sourcing your code
- Distribute bigRAG as part of a commercial offering
- Modify bigRAG and keep modifications private

The only requirements: preserve copyright notices and the LICENSE file.

### 25.2 Repository Structure

```
bigrag/
├── Cargo.toml              # Workspace manifest
├── Cargo.lock
├── crates/
│   ├── bigrag-core/        # Storage engine (BSF, WAL, compaction)
│   ├── bigrag-index/       # ANN + BM25 indexes
│   ├── bigrag-filter/      # Filter DSL engine
│   ├── bigrag-api/         # HTTP API server (Axum)
│   ├── bigrag-auth/        # API key + JWT auth
│   ├── bigrag-cache/       # DRAM + NVMe cache management
│   ├── bigrag-storage/     # Object storage abstraction (S3/GCS/Azure/local)
│   ├── bigrag-cli/         # CLI tool
│   ├── bigrag-bench/       # Benchmark binary
│   └── bigrag-migrate/     # Migration tools
├── sdks/
│   ├── python/             # Python SDK
│   ├── typescript/         # TypeScript/Node SDK
│   ├── go/                 # Go SDK
│   ├── java/               # Java SDK
│   └── ruby/               # Ruby SDK
├── ui/                     # Admin dashboard (Next.js)
├── docs/                   # Documentation
├── docker/                 # Dockerfiles
│   ├── Dockerfile          # Main server image
│   └── Dockerfile.embed    # Embedding sidecar
├── helm/                   # Kubernetes Helm chart
├── tests/                  # Integration tests
├── benches/                # Benchmark datasets + scripts
├── .github/
│   ├── workflows/          # CI/CD
│   └── ISSUE_TEMPLATE/     # Bug report, feature request templates
├── CLAUDE.md               # AI coding instructions
├── CONTRIBUTING.md
├── SECURITY.md
└── README.md
```

### 25.3 Development Workflow

1. **GitHub Issues** for bug reports and feature requests
2. **GitHub Discussions** for questions and community help
3. **PRs** must include:
   - Tests for new functionality
   - Documentation updates
   - Benchmark results if changing performance-critical paths
4. **Release cadence:** Monthly minor releases, weekly patch releases
5. **Security issues:** Reported via GitHub Security Advisories (private until fix ships)

### 25.4 Community Channels

- **Discord:** Primary community chat, #help, #dev, #announcements
- **GitHub Discussions:** Long-form questions and design discussions
- **Monthly community calls:** Video calls open to all contributors

### 25.5 Cloud Edition (Commercial)

bigRAG Cloud is a managed version of bigRAG with:
- Fully managed infrastructure
- Global CDN and edge caching
- Multi-region replication
- SLA guarantees
- Unlimited support

bigRAG Cloud uses the same open-source engine (no forked proprietary additions). The cloud edition only adds operational tooling (auto-scaling, monitoring, billing UI).

---

## 26. Implementation Roadmap

### Phase 0 — Foundation (Weeks 1-6)

**Goal:** Working bigRAG binary with basic upsert/query, local filesystem backend.

| Component | Owner | Priority |
|-----------|-------|---------|
| `bigrag-storage`: local FS backend | Storage team | P0 |
| `bigrag-core`: WAL writer + LSM structure | Core team | P0 |
| `bigrag-core`: BSF format encoder/decoder | Core team | P0 |
| `bigrag-filter`: filter DSL parser + evaluator | Query team | P0 |
| `bigrag-api`: HTTP server skeleton (Axum) | API team | P0 |
| `bigrag-api`: upsert, query, delete endpoints | API team | P0 |
| `bigrag-index`: brute-force kNN (for correctness baseline) | Index team | P0 |
| Docker image + docker-compose | DevOps | P0 |
| Python SDK v0.1 | SDK team | P0 |
| Basic README + quickstart | Docs | P0 |

### Phase 1 — Core Feature Parity (Weeks 7-16)

**Goal:** Feature parity with turbopuffer's core API.

| Component | Owner | Priority |
|-----------|-------|---------|
| `bigrag-storage`: S3 backend | Storage team | P0 |
| `bigrag-storage`: MinIO backend | Storage team | P0 |
| `bigrag-index`: SPFresh ANN index | Index team | P0 |
| `bigrag-index`: BM25 full-text search (FTS v1) | Index team | P0 |
| `bigrag-index`: hybrid query (RRF fusion) | Index team | P0 |
| `bigrag-core`: compaction (L0/L1/L2) | Core team | P0 |
| `bigrag-core`: conditional writes | Core team | P1 |
| `bigrag-core`: patch / delete-by-filter | Core team | P1 |
| `bigrag-auth`: API key management | Auth team | P0 |
| `bigrag-cache`: DRAM cache (LRU) | Cache team | P1 |
| `bigrag-cache`: NVMe cache | Cache team | P1 |
| Namespace management (list, copy, export) | API team | P1 |
| Schema system (online updates) | Core team | P1 |
| TypeScript SDK | SDK team | P1 |
| Go SDK | SDK team | P1 |
| Prometheus metrics | Observability | P1 |
| Structured logging | Observability | P1 |

### Phase 2 — Advanced Features (Weeks 17-28)

**Goal:** Surpass turbopuffer in developer experience and features.

| Component | Owner | Priority |
|-----------|-------|---------|
| `bigrag-storage`: GCS backend | Storage team | P1 |
| `bigrag-storage`: Azure Blob backend | Storage team | P1 |
| `bigrag-index`: BM25 FTS v2 (MAXSCORE/WAND) | Index team | P0 |
| `bigrag-index`: HNSW (alternative to SPFresh) | Index team | P1 |
| `bigrag-index`: regex trie index | Index team | P1 |
| Multi-vector columns | Index team | P1 |
| Aggregations (count, sum, group_by, distinct) | Query team | P1 |
| Cursor-based pagination | API team | P1 |
| Namespace copy cross-region | Core team | P1 |
| Point-in-time recovery | Core team | P2 |
| Admin dashboard (Next.js) | Frontend team | P1 |
| Recall monitoring + auto-tuning | Index team | P1 |
| LangChain integration | SDK team | P1 |
| LlamaIndex integration | SDK team | P1 |
| Java/Kotlin SDK | SDK team | P2 |
| Ruby SDK | SDK team | P2 |
| Helm chart | DevOps | P1 |
| turbopuffer compatibility mode | API team | P1 |

### Phase 3 — Scale & Polish (Weeks 29-40)

**Goal:** Production-hardened, scale-tested, fully documented.

| Component | Priority |
|-----------|---------|
| Filter-aware HNSW (pre-filter ANN) | P1 |
| Document-level access control (key filter rules) | P1 |
| JWT authentication | P1 |
| CMEK support (KMS integration) | P2 |
| Horizontal read replica scaling | P1 |
| Distributed compaction (multiple compactor nodes) | P2 |
| Scheduled backup jobs | P2 |
| WASM embedding sidecar | P2 |
| ANN benchmark suite + publish results | P1 |
| Geo-filtering (lat/lng radius, bounding box) | P2 |
| Streaming API (SSE) for large result sets | P2 |
| Migration tools (Pinecone, Qdrant, Weaviate) | P2 |
| Load testing (10M namespaces, 100B vectors) | P0 |
| Security audit | P0 |

---

## 27. Engineering Team Structure

### 27.1 Recommended Team Composition

**Minimum viable team (Phase 0-1): 4-6 engineers**

| Role | Headcount | Responsibilities |
|------|-----------|-----------------|
| **Storage & Core Engine (Rust)** | 2 | WAL, BSF format, LSM compaction, object store backends |
| **Index & Search (Rust)** | 2 | SPFresh/HNSW ANN, BM25/FTS, filter engine, hybrid fusion |
| **API & SDK** | 1 | HTTP API (Axum), Python/TypeScript SDKs, API compatibility |
| **DevOps & Infra** | 1 | Docker, Kubernetes, CI/CD, benchmarks |

**Growth team (Phase 2-3): 8-12 engineers**

Add:
- 1 Frontend (Admin dashboard, Next.js)
- 1 Developer Experience (documentation, tutorials, LangChain/LlamaIndex integrations)
- 1 Observability (metrics, dashboards, alerting)
- 1-2 QA/Testing (integration tests, compatibility testing, benchmarks)

### 27.2 Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Core engine | **Rust** | Memory safety, performance, no GC pauses |
| HTTP API | **Axum** (Rust) | Async, low overhead, Tower middleware ecosystem |
| Object storage | **object_store** crate | Unified S3/GCS/Azure/MinIO abstraction |
| Serialization | **rkyv** / **serde_json** | Zero-copy deserialization for BSF; JSON for API |
| Compression | **lz4_flex**, **zstd** | LZ4 for speed-critical paths; ZSTD for storage efficiency |
| ANN | Custom SPFresh (Rust) + **hnswlib** bindings | Reference implementation |
| BM25 | Custom (Rust), tantivy-inspired | Full control over MAXSCORE/WAND implementation |
| SIMD | **std::simd** (portable_simd) + AVX2 intrinsics | Vectorized distance computation |
| Async runtime | **Tokio** | Production-grade async Rust |
| CLI | **clap** | Ergonomic CLI with completions |
| Admin UI | **Next.js** + **shadcn/ui** | Rapid development, good defaults |
| Testing | **proptest** (property tests) + **criterion** (benchmarks) | Comprehensive correctness + perf testing |
| CI/CD | **GitHub Actions** | Self-hosted runners for benchmarks |

---

## 28. Appendix: turbopuffer Feature Parity Matrix

| Feature | turbopuffer | bigRAG | Notes |
|---------|------------|--------|-------|
| Vector ANN search (SPFresh) | ✅ | ✅ | |
| Vector kNN exact search | ✅ | ✅ | |
| BM25 full-text search | ✅ | ✅ | |
| Hybrid search (RRF fusion) | ✅ | ✅ | |
| Multi-query (16x parallel) | ✅ | ✅ | |
| Metadata filtering (full DSL) | ✅ | ✅ | |
| Array filter operators | ✅ | ✅ | AnyLt, ContainsAny, etc. |
| Regex/Glob filters | ✅ | ✅ | |
| Phrase matching (ContainsTokenSequence) | ✅ | ✅ | |
| Conditional writes | ✅ | ✅ | |
| Patch by filter | ✅ | ✅ | |
| Delete by filter | ✅ | ✅ | |
| Column format (upsert) | ✅ | ✅ | |
| f16 vectors | ✅ | ✅ | |
| Multiple vector columns | ✅ beta | ✅ | |
| Nested attributes | Roadmap | ✅ v2 | |
| Aggregations (count, sum, group_by) | ✅ | ✅ | |
| Distinct aggregation | Roadmap | ✅ | |
| Min/Max aggregation | Roadmap | ✅ | |
| Cursor pagination | Implicit | ✅ | Explicit cursor support |
| Namespace list with prefix | ✅ | ✅ | |
| Cross-region namespace copy | ✅ | ✅ | |
| Namespace export (Parquet) | Manual | ✅ | Built-in export endpoint |
| Recall endpoint | ✅ | ✅ | |
| Recall auto-tuning | ✅ (auto) | ✅ (auto + manual) | |
| Index state visibility | ✅ | ✅ | |
| Indexing state in metadata | ✅ | ✅ | |
| Read replicas | ✅ beta | ✅ | |
| Object storage backend (S3/GCS) | ✅ | ✅ | |
| Azure Blob backend | BYOC only | ✅ | |
| MinIO backend | No | ✅ | Self-hosted |
| Local filesystem backend | No | ✅ | Dev/testing |
| Self-hosted Docker | No | ✅ | Core differentiator |
| Open source | No | ✅ | Apache 2.0 |
| HNSW index (exposed) | No | ✅ | Optional alternative |
| Filter-aware ANN (pre-filter) | No | ✅ v2 | Planned Phase 3 |
| Built-in admin dashboard | Roadmap | ✅ | |
| LangChain integration | Community | ✅ Official | |
| LlamaIndex integration | Community | ✅ Official | |
| Geo-filtering | No | ✅ v2 | Planned Phase 3 |
| Backup scheduler | Manual | ✅ Built-in | |
| Point-in-time recovery | No | ✅ | |
| turbopuffer API compatibility | — | ✅ Compat mode | Drop-in replacement |
| WASM embedding sidecar | No | ✅ v2 | Optional |
| JWT authentication | No | ✅ | |
| API key namespace scoping | No | ✅ | Per-tenant key isolation |
| Document-level access control | No | ✅ | Key-filter rules |
| Prometheus metrics | No | ✅ | |
| Structured JSON logging | No | ✅ | |
| ANN recall monitoring + auto-tuning | ✅ | ✅ | |
| SOC2 compliance | ✅ (managed) | Operator-managed | |
| GDPR | ✅ (managed) | Supported (operator-managed) | |
| HIPAA BAA | ✅ Scale plan | N/A (self-hosted) | |
| CMEK | ✅ Enterprise | ✅ KMS integration | |

---

*Document ends. Total features specified: 200+. Implementation phases: 3. Timeline: 40 weeks to production-ready v1.*

*Prepared by: Research Engineers 1-5, Team Lead, Product Manager*
*Research date: 2026-03-28*
*Next step: Create implementation plan (writing-plans skill)*
