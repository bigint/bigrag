# Turbopuffer Client SDKs, Integrations, and Ecosystem
## Comprehensive Research Report - Research Engineer 5

---

## Table of Contents

1. [SDK Overview & Generation Strategy](#1-sdk-overview--generation-strategy)
2. [Python SDK](#2-python-sdk)
3. [TypeScript/JavaScript SDK](#3-typescriptjavascript-sdk)
4. [Go SDK](#4-go-sdk)
5. [Java SDK](#5-java-sdk)
6. [Ruby SDK](#6-ruby-sdk)
7. [Rust SDK (Community)](#7-rust-sdk-community)
8. [REST API - Complete HTTP Specification](#8-rest-api---complete-http-specification)
9. [Authentication & API Key Management](#9-authentication--api-key-management)
10. [SDK Features - Cross-Cutting Concerns](#10-sdk-features---cross-cutting-concerns)
11. [LangChain Integration](#11-langchain-integration)
12. [LlamaIndex Integration](#12-llamaindex-integration)
13. [Mastra Integration](#13-mastra-integration)
14. [Vectorize Integration](#14-vectorize-integration)
15. [Daft Integration](#15-daft-integration)
16. [MCP Server (AI Assistant Integration)](#16-mcp-server-ai-assistant-integration)
17. [Puffgres (Postgres CDC)](#17-puffgres-postgres-cdc)
18. [Turbopuffer GUI (Community Desktop Client)](#18-turbopuffer-gui-community-desktop-client)
19. [Benchmark Tool](#19-benchmark-tool)
20. [Import/Export & Data Migration](#20-importexport--data-migration)
21. [Monitoring & Observability](#21-monitoring--observability)
22. [Webhooks/Events](#22-webhooksevents)
23. [Embedding Model Integrations](#23-embedding-model-integrations)
24. [Re-Ranker Integrations](#24-re-ranker-integrations)
25. [Regions & Infrastructure](#25-regions--infrastructure)
26. [Security & Compliance](#26-security--compliance)
27. [Pricing Structure](#27-pricing-structure)
28. [OpenAPI Specification](#28-openapi-specification)
29. [Roadmap & Changelog Highlights](#29-roadmap--changelog-highlights)
30. [Implications for bigRAG](#30-implications-for-bigrag)

---

## 1. SDK Overview & Generation Strategy

Turbopuffer uses **Stainless** (stainless.com) for automated SDK generation from their OpenAPI specification. All official SDKs are generated from a single OpenAPI spec (hosted at github.com/turbopuffer/turbopuffer-openapi), ensuring consistency across languages.

### Official SDKs (5 languages):
| Language | Package | Repository | Version (as of March 2026) |
|----------|---------|------------|---------------------------|
| Python | `turbopuffer` (PyPI) | github.com/turbopuffer/turbopuffer-python | 1.16.2 |
| TypeScript | `@turbopuffer/turbopuffer` (npm) | github.com/turbopuffer/turbopuffer-typescript | 1.19.0 |
| Go | `github.com/turbopuffer/turbopuffer-go` | github.com/turbopuffer/turbopuffer-go | 1.20.0 |
| Java | `com.turbopuffer:turbopuffer-java` (Maven) | github.com/turbopuffer/turbopuffer-java | 1.20.0 |
| Ruby | `turbopuffer` (RubyGems) | github.com/turbopuffer/turbopuffer-ruby | 1.18.0 |

### Community SDKs:
| Language | Package | Repository |
|----------|---------|------------|
| Rust | `turbopuffer-client` (crates.io) | github.com/ragkit/turbopuffer-client |

### Stainless SDK Generation Benefits (measured by turbopuffer):
- Python sync upsert: 1.88s -> 1.13s (1.66x faster)
- Python async: 4.34s -> 2.57s (1.69x faster)
- TypeScript query_scale: 3,436ms -> 2,778ms (1.24x faster via Undici backend)
- All 5 SDKs achieved v1.0 production readiness
- SDK release cycles compressed from weeks to days
- 100% documentation coverage

---

## 2. Python SDK

### Installation
```bash
pip install turbopuffer
# For aiohttp async support:
pip install turbopuffer[aiohttp]
```

**Requirements:** Python 3.9+

### Client Initialization

#### Synchronous Client
```python
import os
from turbopuffer import Turbopuffer

tpuf = Turbopuffer(
    region="gcp-us-central1",
    api_key=os.environ.get("TURBOPUFFER_API_KEY"),
)
```

#### Asynchronous Client (httpx-based)
```python
import os
import asyncio
from turbopuffer import AsyncTurbopuffer

tpuf = AsyncTurbopuffer(
    region="gcp-us-central1",
    api_key=os.environ.get("TURBOPUFFER_API_KEY"),
)
```

#### Asynchronous Client (aiohttp-based, better concurrency)
```python
import os
import asyncio
from turbopuffer import DefaultAioHttpClient, AsyncTurbopuffer

async def main() -> None:
    async with AsyncTurbopuffer(
        api_key=os.environ.get("TURBOPUFFER_API_KEY"),
        http_client=DefaultAioHttpClient(),
    ) as client:
        response = await client.namespaces.write(
            namespace="products",
            distance_metric="cosine_distance",
            upsert_rows=[
                {
                    "id": "2108ed60-6851-49a0-9016-8325434f3845",
                    "vector": [0.1, 0.2],
                }
            ],
        )
        print(response.rows_affected)

asyncio.run(main())
```

### Configuration Options
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `region` | string | None | API region (e.g., "gcp-us-central1") |
| `api_key` | string | `TURBOPUFFER_API_KEY` env var | Authentication key |
| `max_retries` | int | 2 | Number of automatic retries |
| `timeout` | float / httpx.Timeout | 60.0 | Request timeout in seconds |
| `http_client` | object | None | Custom HTTP client (e.g., DefaultAioHttpClient) |

### Core Operations

#### Namespace Operations
```python
ns = tpuf.namespace("example")
```

#### Vector Search (ANN)
```python
vector_result = ns.query(
    rank_by=("vector", "ANN", [0.1, 0.2]),
    top_k=10,
    filters=("And", (("name", "Eq", "foo"), ("public", "Eq", 1))),
    include_attributes=["name"],
)
print(vector_result.rows)
```

#### Full-Text Search (BM25)
```python
fts_result = ns.query(
    top_k=10,
    filters=("name", "Eq", "foo"),
    rank_by=("text", "BM25", "quick walrus"),
)
print(fts_result.rows)
```

#### Write/Upsert
```python
response = client.namespaces.write(
    namespace="namespace",
    distance_metric="cosine_distance",
    upsert_rows=[
        {"id": 1, "vector": [0.1, 0.2], "name": "foo"},
    ],
    schema={"text": {"type": "string", "full_text_search": True}},
)
```

#### Delete Namespace
```python
ns.delete_all()
```

#### Recall Testing
```python
recall = ns.recall(num=5, top_k=10)
```

### Pagination

#### Auto-Paginating Iterator (Sync)
```python
all_namespaces = []
for ns in client.namespaces(prefix="products"):
    all_namespaces.append(ns)
```

#### Auto-Paginating Iterator (Async)
```python
async for ns in client.namespaces(prefix="products"):
    all_namespaces.append(ns)
```

#### Manual Pagination
```python
first_page = await client.namespaces(prefix="products")
if first_page.has_next_page():
    next_page = await first_page.get_next_page()
    print(f"number of items: {len(next_page.namespaces)}")
```

### Error Handling
```python
import turbopuffer
from turbopuffer import Turbopuffer

client = Turbopuffer()

try:
    client.namespaces(prefix="foo")
except turbopuffer.APIConnectionError as e:
    print("The server could not be reached")
    print(e.__cause__)
except turbopuffer.RateLimitError as e:
    print("A 429 status code was received; we should back off a bit.")
except turbopuffer.APIStatusError as e:
    print("Another non-200-range status code was received")
    print(e.status_code)
    print(e.response)
```

### Error Types
| Error Class | HTTP Status |
|-------------|-------------|
| `BadRequestError` | 400 |
| `AuthenticationError` | 401 |
| `PermissionDeniedError` | 403 |
| `NotFoundError` | 404 |
| `UnprocessableEntityError` | 422 |
| `RateLimitError` | 429 |
| `InternalServerError` | >= 500 |
| `APIConnectionError` | Network error |
| `APITimeoutError` | Timeout |

### Advanced Features

#### Retry Configuration
```python
# Configure default for all requests
client = Turbopuffer(max_retries=0)

# Override per-request
client.with_options(max_retries=5).namespaces(prefix="foo")
```

#### Timeout Configuration
```python
import httpx
from turbopuffer import Turbopuffer

# Float value (seconds)
client = Turbopuffer(timeout=20.0)

# Granular control
client = Turbopuffer(
    timeout=httpx.Timeout(60.0, read=5.0, write=10.0, connect=2.0)
)

# Per-request override
client.with_options(timeout=5.0).namespaces(prefix="foo")
```

#### Logging
```bash
export TURBOPUFFER_LOG=info    # or debug for verbose
```

#### Raw Response Access
```python
response = client.with_raw_response.namespaces(prefix="foo")
print(response.headers.get('X-My-Header'))
parsed = response.parse()
```

#### Distinguishing Null vs Missing Fields
```python
if response.my_field is None:
    if 'my_field' not in response.model_fields_set:
        print('Field missing entirely from JSON')
    else:
        print('Field explicitly set to null')
```

### Type System
- Nested request parameters use **TypedDict**
- Responses are **Pydantic models** with helpers: `model.to_json()`, `model.to_dict()`

---

## 3. TypeScript/JavaScript SDK

### Installation
```bash
npm install @turbopuffer/turbopuffer
```

**Requirements:** TypeScript >= 4.9, Node.js 20 LTS+, Deno v1.28.0+, Bun 1.0+, Cloudflare Workers, Vercel Edge Runtime

### Client Initialization
```typescript
import Turbopuffer from '@turbopuffer/turbopuffer';

const tpuf = new Turbopuffer({
  apiKey: process.env['TURBOPUFFER_API_KEY'],
});
```

### Core Operations

#### Vector Search
```typescript
const ns = tpuf.namespace("example");

const vectorResult = await ns.query({
  rank_by: ["vector", "ANN", [0.1, 0.2]],
  top_k: 10,
  filters: [
    "And",
    [
      ["name", "Eq", "foo"],
      ["public", "Eq", 1],
    ],
  ],
  include_attributes: ["name"],
});
console.log(vectorResult.rows);
```

#### Full-Text Search
```typescript
const ftsResult = await ns.query({
  top_k: 10,
  filters: ["name", "Eq", "foo"],
  rank_by: ["text", "BM25", "quick walrus"],
});
```

#### Delete Namespace
```typescript
await ns.deleteAll();
```

#### Recall Testing
```typescript
const recall = await ns.recall({ num: 5, top_k: 10 });
```

### Type System
```typescript
const params: Turbopuffer.NamespacesParams = { prefix: 'foo' };
const [namespaceSummary]: [Turbopuffer.NamespaceSummary] =
  await client.namespaces(params);
```

### Error Handling
```typescript
try {
  await client.namespaces({ prefix: 'foo' });
} catch (err) {
  if (err instanceof Turbopuffer.APIError) {
    console.log(err.status);
    console.log(err.name);
    console.log(err.headers);
  }
}
```

### Retry & Timeout Configuration
```typescript
// Global configuration
const client = new Turbopuffer({
  maxRetries: 0,
  timeout: 20 * 1000, // 20 seconds
});

// Per-request override
await client.namespaces({ prefix: 'foo' }, { maxRetries: 5, timeout: 5 * 1000 });
```

### Auto-Pagination
```typescript
// for-await
for await (const namespaceSummary of client.namespaces({ prefix: 'products' })) {
  console.log(namespaceSummary);
}

// Manual
let page = await client.namespaces({ prefix: 'products' });
while (page.hasNextPage()) {
  page = await page.getNextPage();
}
```

### Raw Response Access
```typescript
const response = await client.namespaces({ prefix: 'foo' }).asResponse();
console.log(response.headers.get('X-My-Header'));

const { data: namespaces, response: raw } = await client
  .namespaces({ prefix: 'foo' })
  .withResponse();
```

### Logging
```typescript
const client = new Turbopuffer({
  logLevel: 'debug', // 'debug', 'info', 'warn', 'error', 'off'
});

// Custom logger (pino, winston, bunyan, consola, signale, @std/log)
import pino from 'pino';
const logger = pino();
const client = new Turbopuffer({
  logger: logger.child({ name: 'Turbopuffer' }),
  logLevel: 'debug',
});
```

### Custom/Undocumented Requests
```typescript
await client.post('/some/path', {
  body: { some_prop: 'foo' },
  query: { some_query_arg: 'bar' },
});
// Available: client.get, client.post, client.put, client.patch, client.delete
```

### Compression
```typescript
const client = new Turbopuffer({
  compression: true, // gzip compression for network-constrained apps
});
```

---

## 4. Go SDK

### Installation
```go
import "github.com/turbopuffer/turbopuffer-go"
```

Pin version:
```bash
go get -u 'github.com/turbopuffer/turbopuffer-go@v1.20.0'
```

**Requirements:** Go 1.22+

### Client Initialization
```go
package main

import (
    "context"
    "os"
    "github.com/turbopuffer/turbopuffer-go"
    "github.com/turbopuffer/turbopuffer-go/option"
)

func main() {
    ctx := context.Background()
    tpuf := turbopuffer.NewClient(
        option.WithAPIKey(os.Getenv("TURBOPUFFER_API_KEY")),
        option.WithRegion("gcp-us-central1"),
    )
    ns := tpuf.Namespace("example")
}
```

### Core Operations

#### Vector Search
```go
queryRes, err := ns.Query(ctx, turbopuffer.NamespaceQueryParams{
    RankBy: turbopuffer.NewRankByVector("vector", []float32{0.1, 0.2}),
    TopK:   turbopuffer.Int(10),
    Filters: turbopuffer.NewFilterAnd([]turbopuffer.Filter{
        turbopuffer.NewFilterEq("name", "foo"),
        turbopuffer.NewFilterEq("public", 1),
    }),
    IncludeAttributes: turbopuffer.IncludeAttributesParam{
        StringArray: []string{"name"},
    },
})
```

#### Full-Text Search
```go
ftsRes, err := ns.Query(ctx, turbopuffer.NamespaceQueryParams{
    TopK:    turbopuffer.Int(10),
    Filters: turbopuffer.NewFilterEq("name", "foo"),
    RankBy:  turbopuffer.NewRankByTextBM25("text", "quick walrus"),
})
```

#### Delete Namespace
```go
err := ns.DeleteAll(ctx)
```

#### Recall Testing
```go
recall, err := ns.Recall(ctx, turbopuffer.NamespaceRecallParams{
    Num:  turbopuffer.Int(5),
    TopK: turbopuffer.Int(10),
})
```

### Parameter Types
- Required primitive fields: `json:"...,required"` (always serialized)
- Optional primitive fields: `param.Opt[T]` with constructors `turbopuffer.String()`, `turbopuffer.Int()`, etc.
- Send null: `param.Null[T]()`, `param.NullStruct[T]()`
- Extra fields: `params.SetExtraFields(map[string]any{...})`

### Response Objects
All response fields are ordinary value types. Special `JSON` struct field provides metadata:
```go
res.JSON.Owners.Valid()      // true if not null and present
res.JSON.Name.Raw()          // raw JSON string
res.JSON.ExtraFields["key"]  // undocumented properties
```

### Auto-Pagination
```go
iter := client.NamespacesAutoPaging(ctx, turbopuffer.NamespacesParams{
    Prefix: turbopuffer.String("products"),
})
for iter.Next() {
    namespaceSummary := iter.Current()
    fmt.Printf("%+v\n", namespaceSummary)
}
if err := iter.Err(); err != nil {
    panic(err.Error())
}
```

### Error Handling
```go
_, err := client.Namespaces(ctx, turbopuffer.NamespacesParams{
    Prefix: turbopuffer.String("foo"),
})
if err != nil {
    var apierr *turbopuffer.Error
    if errors.As(err, &apierr) {
        println(string(apierr.DumpRequest(true)))
        println(string(apierr.DumpResponse(true)))
    }
}
```

### Timeouts
```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
defer cancel()
// option.WithRequestTimeout sets per-retry timeout
client.Namespaces(ctx, params, option.WithRequestTimeout(20*time.Second))
```

### Request Options (functional options pattern)
```go
client := turbopuffer.NewClient(
    option.WithHeader("X-Some-Header", "custom_header_info"),
)
// option.WithDebugLog(nil) for debugging
```

---

## 5. Java SDK

### Installation

**Gradle:**
```kotlin
implementation("com.turbopuffer:turbopuffer-java:1.20.0")
```

**Maven:**
```xml
<dependency>
  <groupId>com.turbopuffer</groupId>
  <artifactId>turbopuffer-java</artifactId>
  <version>1.20.0</version>
</dependency>
```

**Requirements:** Java 8+

### Client Configuration
| Setting | System Property | Environment Variable | Required |
|---------|----------------|---------------------|----------|
| API Key | `turbopuffer.apiKey` | `TURBOPUFFER_API_KEY` | Yes |
| Region | `turbopuffer.region` | `TURBOPUFFER_REGION` | No |
| Base URL | `turbopuffer.baseUrl` | `TURBOPUFFER_BASE_URL` | Yes (defaults to region URL) |

### Client Initialization
```java
TurbopufferClient client = TurbopufferOkHttpClient.builder()
    .fromEnv()
    .defaultNamespace("My Namespace")
    .build();
```

### Key Features
- All classes are immutable; builders support `toBuilder()` for modifications
- Async via `client.async()` returning `CompletableFuture`
- Raw responses via `client.withRawResponse()` returning `HttpResponseFor<T>`
- Auto-pagination via `autoPager()` (sync: `Iterable`, async: `AsyncStreamResponse`)

### Error Types
| Error | Status |
|-------|--------|
| `BadRequestException` | 400 |
| `UnauthorizedException` | 401 |
| `PermissionDeniedException` | 403 |
| `NotFoundException` | 404 |
| `UnprocessableEntityException` | 422 |
| `RateLimitException` | 429 |
| `InternalServerException` | 5xx |
| `TurbopufferIoException` | Network errors |

### Recall Testing
```java
var recall = ns.recall(NamespaceRecallParams.builder()
    .num(5).topK(10).build());
```

---

## 6. Ruby SDK

### Installation
```ruby
# Gemfile
gem "turbopuffer", "~> 1.18.0"
```

**Requirements:** Ruby 3.2.0+

### Client Initialization
```ruby
require "turbopuffer"

tpuf = Turbopuffer::Client.new(
  api_key: ENV["TURBOPUFFER_API_KEY"],
  region: "gcp-us-central1",
)

ns = tpuf.namespace("example")
```

### Core Operations

#### Vector Search
```ruby
result = ns.query(
  rank_by: ["vector", "ANN", [0.1, 0.2]],
  top_k: 10,
  filters: ["And", [["name", "Eq", "foo"], ["public", "Eq", 1]]],
  include_attributes: ["name"],
)
puts result.rows
```

#### Full-Text Search
```ruby
result = ns.query(
  top_k: 10,
  filters: ["name", "Eq", "foo"],
  rank_by: ["text", "BM25", "quick walrus"],
)
```

#### Write with Sorbet Types
```ruby
turbopuffer.namespace("products").write(
  distance_metric: "cosine_distance",
  upsert_rows: [Turbopuffer::Row.new(
    id: "2108ed60-6851-49a0-9016-8325434f3845",
    vector: [0.1, 0.2]
  )]
)
```

### Configuration
| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 4 | Auto-retry count |
| `timeout` | 60 | Timeout in seconds |
| `compression` | false | Enable gzip compression |

### Concurrency
- `Turbopuffer::Client` instances are threadsafe
- Fork-safe only when no in-flight HTTP requests
- Default HTTP connection pool size: 99
- Recommended: instantiate client once per application

### Sorbet Integration
- Comprehensive RBI definitions provided
- No sorbet-runtime dependency
- Enums use "tagged symbols" (e.g., `Turbopuffer::DistanceMetric::COSINE_DISTANCE`)

### Error Types
Same as Python plus:
| Error | Cause |
|-------|-------|
| `ConflictError` | HTTP 409 |
| `APITimeoutError` | Timeout |
| `APIConnectionError` | Network error |

---

## 7. Rust SDK (Community)

**Not official.** Published by ragkit, not turbopuffer.

### Installation
```toml
[dependencies]
turbopuffer-client = "0.0.3"
```

### Usage
```rust
let client = turbopuffer_client::Client::new(&api_key);
let ns = client.namespace("test");

// Upsert
let body = json!({
    "ids": [1, 2, 3, 4],
    "vectors": [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3], [0.4, 0.4]],
    "attributes": {
        "my-string": ["one", null, "three", "four"],
        "my-uint": [12, null, 84, 39],
    }
});
let res = ns.upsert(&body).await.unwrap();

// Query
let query = json!({
    "vector": [0.105, 0.1],
    "distance_metric": "euclidean_squared",
    "top_k": 1,
    "include_vectors": true,
    "include_attributes": ["my-string"]
});
let res = ns.query(&query).await.unwrap();

// Delete
let res = ns.delete().await.unwrap();
```

**Note:** The library does NOT validate JSON bodies -- it passes them directly to turbopuffer. It uses the v1 API (deprecated), not v2. Very minimal API surface. Version 0.0.3 indicates early development.

A second community Rust client called **rs-puff** was part of the puffgres project (now archived).

---

## 8. REST API - Complete HTTP Specification

### Base URL Pattern
```
https://{region}.turbopuffer.com
```
Example: `https://gcp-us-central1.turbopuffer.com`

### Authentication
All requests require:
```
Authorization: Bearer <API_KEY>
```

### Encoding
- JSON for all request/response payloads
- Standard HTTP compression headers supported (but recommended to disable - clients are typically CPU constrained, not bandwidth constrained)

### Error Response Format
```json
{"status": "error", "error": "an error message"}
```

### Complete Endpoint Reference

#### 1. List Namespaces
```
GET /v1/namespaces
```
**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | None | Pagination cursor from `next_cursor` |
| `prefix` | string | None | Filter namespaces by prefix |
| `page_size` | int | 100 | Results per page (max 1000) |

**Response:**
```json
{
  "namespaces": [{"id": "my-namespace"}],
  "next_cursor": "abc123"
}
```

#### 2. Get Namespace Metadata
```
GET /v1/namespaces/:namespace/metadata
```
**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `schema` | object | Attribute type definitions and indexing config |
| `approx_logical_bytes` | integer | Approximate logical bytes in namespace |
| `approx_row_count` | integer | Approximate document count |
| `created_at` | string (ISO 8601) | Creation timestamp |
| `updated_at` | string (ISO 8601) | Last write timestamp |
| `encryption` | object | `{"mode": "default"}` or `{"mode": "customer-managed", "key_name": "..."}` |
| `index` | object | `{"status": "up-to-date"}` or `{"status": "updating", "unindexed_bytes": N}` |

**Billing:** Billed as a query returning zero rows.

#### 3. Get Namespace Schema
```
GET /v1/namespaces/:namespace/schema
```

#### 4. Update Namespace Schema
```
POST /v1/namespaces/:namespace/schema
```

#### 5. Warm Cache
```
GET /v1/namespaces/:namespace/hint_cache_warm
```
Pre-warms the cache for a namespace to reduce cold query latency.

#### 6. Recall Testing
```
POST /v1/namespaces/:namespace/_debug/recall
```
**Request Body:**
```json
{
  "num": 25,
  "top_k": 10,
  "filters": ["name", "Eq", "foo"]
}
```
**Response:**
```json
{
  "avg_recall": 0.95,
  "avg_exhaustive_count": 10,
  "avg_ann_count": 10
}
```
**Billing:** One query per sample per 100K documents when avg_recall >= 0.9.

#### 7. Write Documents
```
POST /v2/namespaces/:namespace
```
**Request Body Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `distance_metric` | string | `cosine_distance` or `euclidean_squared` (required unless copy_from_namespace) |
| `upsert_rows` | array | Row-based upsert: `[{"id": 1, "vector": [...], "attr": "val"}]` |
| `upsert_columns` | object | Column-based upsert |
| `patch_rows` | array | Partial updates (cannot patch vector) |
| `patch_columns` | object | Column-based partial updates |
| `deletes` | array | Document IDs to delete |
| `delete_by_filter` | filter | Delete documents matching filter |
| `patch_by_filter` | object | Patch documents matching filter |
| `upsert_condition` | filter | Conditional write |
| `patch_condition` | filter | Conditional patch |
| `delete_condition` | filter | Conditional delete |
| `schema` | object | Attribute type and indexing config |
| `encryption` | object | CMEK configuration |
| `copy_from_namespace` | string/object | Server-side namespace copy |
| `return_affected_ids` | boolean | Return arrays of affected IDs (default: false) |
| `disable_backpressure` | boolean | Disable HTTP 429 for bulk loads (default: false) |

**Response:**
```json
{
  "rows_affected": 4,
  "rows_upserted": 3,
  "rows_patched": 1,
  "rows_deleted": 0,
  "billing": {...},
  "performance": {...}
}
```
**Max payload:** 512 MB per request.

#### 8. Query Documents
```
POST /v2/namespaces/:namespace/query
```
**Request Body Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rank_by` | array | Ranking method (see below) |
| `top_k` | number | Alias for `limit.total` (max 10,000) |
| `limit` | number/object | Simple limit or `{"per": {"attributes": [...], "limit": N}, "total": N}` |
| `filters` | array | Filter expression (see filtering section) |
| `include_attributes` | array/boolean | Attributes to return (true = all) |
| `exclude_attributes` | array | Attributes to exclude |
| `aggregate_by` | object | Aggregation functions |
| `group_by` | array | Group aggregation results |
| `queries` | array | Multi-query (up to 16 subqueries) |
| `vector_encoding` | string | `"float"` (default) or `"base64"` |
| `consistency` | object | `{"level": "strong"}` (default) or `{"level": "eventual"}` |

**Ranking Methods (`rank_by`):**
| Method | Syntax | Description |
|--------|--------|-------------|
| ANN | `["vector", "ANN", [0.1, 0.2]]` | Approximate nearest neighbor |
| kNN | `["vector", "kNN", [0.1, 0.2]]` | Exact search (requires filters) |
| BM25 | `["text_field", "BM25", "query"]` | Full-text search |
| Order | `["attribute", "asc"/"desc"]` | Sort by attribute |
| Sum | `["Sum", [expr1, expr2]]` | Sum scores |
| Max | `["Max", [expr1, expr2]]` | Max score |
| Product | `["Product", weight, expr]` | Weighted score |
| Saturate | `["Saturate", ["Attribute", "field"], {"midpoint": N}]` | Score mapping |
| Decay | `["Decay", ["Attribute", "field"], {"midpoint": N}]` | Inverse scoring |
| Dist | `["Dist", ["Attribute", "field"], origin]` | Distance scoring |
| Attribute | `["Attribute", "field"]` | Raw attribute value |

**Filter Operators:**
| Operator | Description |
|----------|-------------|
| `Eq` / `NotEq` | Equality (null-safe) |
| `In` / `NotIn` | Array membership |
| `Contains` / `NotContains` | Value in array attribute |
| `ContainsAny` / `NotContainsAny` | Any value in array |
| `Lt`, `Lte`, `Gt`, `Gte` | Comparison |
| `AnyLt`, `AnyLte`, `AnyGt`, `AnyGte` | Element-wise array comparison |
| `Glob` / `IGlob` | Unix glob pattern (case-sensitive/insensitive) |
| `NotGlob` / `NotIGlob` | Inverse glob |
| `Regex` | Regular expression (requires schema) |
| `And`, `Or`, `Not` | Logical operators |
| `ContainsAllTokens` | All tokens present (supports `last_as_prefix`) |
| `ContainsTokenSequence` | Exact token sequence |
| `ContainsAnyToken` | Any token present |

**Response:**
```json
{
  "rows": [
    {"$dist": 1.7, "id": 8, "name": "result"}
  ],
  "billing": {
    "billable_logical_bytes_queried": 1024,
    "billable_logical_bytes_returned": 256
  },
  "performance": {
    "cache_hit_ratio": 0.95,
    "cache_temperature": "hot",
    "server_total_ms": 12,
    "query_execution_ms": 8,
    "exhaustive_search_count": 0,
    "approx_namespace_size": 1000000
  }
}
```

#### 9. Multi-Query
```
POST /v2/namespaces/:namespace/query
```
```json
{
  "queries": [
    {"rank_by": ["vector", "ANN", [0.1, 0.2]], "top_k": 10},
    {"rank_by": ["text", "BM25", "search term"], "top_k": 10}
  ]
}
```
**Response:** `{"results": [{...}, {...}]}`

#### 10. Explain Query
```
POST /v2/namespaces/:namespace/explain_query
```
Returns the query execution plan for debugging.

#### 11. Delete Namespace
```
DELETE /v2/namespaces/:namespace
```
**Response:** `{"status": "ok"}`
**Warning:** Irreversible operation.

### curl Examples

#### Write Documents
```bash
curl -X POST "https://gcp-us-central1.turbopuffer.com/v2/namespaces/my-ns" \
  -H "Authorization: Bearer $TURBOPUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "distance_metric": "cosine_distance",
    "upsert_rows": [
      {"id": 1, "vector": [0.1, 0.2, 0.3], "name": "document one"}
    ]
  }'
```

#### Vector Search
```bash
curl -X POST "https://gcp-us-central1.turbopuffer.com/v2/namespaces/my-ns/query" \
  -H "Authorization: Bearer $TURBOPUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "rank_by": ["vector", "ANN", [0.1, 0.2, 0.3]],
    "top_k": 10,
    "include_attributes": ["name"]
  }'
```

#### Full-Text Search
```bash
curl -X POST "https://gcp-us-central1.turbopuffer.com/v2/namespaces/my-ns/query" \
  -H "Authorization: Bearer $TURBOPUFFER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "rank_by": ["text", "BM25", "search query here"],
    "top_k": 10
  }'
```

#### Delete Namespace
```bash
curl -X DELETE "https://gcp-us-central1.turbopuffer.com/v2/namespaces/my-ns" \
  -H "Authorization: Bearer $TURBOPUFFER_API_KEY"
```

#### List Namespaces
```bash
curl "https://gcp-us-central1.turbopuffer.com/v1/namespaces?prefix=my&page_size=100" \
  -H "Authorization: Bearer $TURBOPUFFER_API_KEY"
```

---

## 9. Authentication & API Key Management

### API Key Format
- Created and managed in the turbopuffer dashboard
- Used as Bearer tokens in HTTP Authorization header
- Format: `tpuf_` prefix followed by key value (based on benchmark tool env var example)

### Authorization Header
```
Authorization: Bearer <API_KEY>
```

### Environment Variable Convention
All SDKs read from:
```
TURBOPUFFER_API_KEY
```

### Key Scoping
Turbopuffer does **not** currently offer granular API key scoping or RBAC at the key level. Document-level access control is implemented by:
1. Storing `user_id` or `group_ids` as attributes on documents
2. Filtering at query time using the requesting user's identity
3. Encoding identifiers as UUIDs for storage efficiency

### Organization Model
- Multi-org linking available (beta, opt-in)
- Separate organizations for dev/staging/prod environments
- `copy_from_namespace` supports cross-organization copies with `source_api_key`

---

## 10. SDK Features - Cross-Cutting Concerns

### Retries (All SDKs)
| SDK | Default Retries | Auto-Retried Errors |
|-----|----------------|---------------------|
| Python | 2 | Connection errors, 408, 409, 429, >= 500 |
| TypeScript | 2 | Connection errors, 408, 409, 429, >= 500 |
| Go | 2 | Connection errors, 408, 409, 429, >= 500 |
| Java | 4 | Connection errors, 408, 409, 429, >= 500 |
| Ruby | 4 | Connection errors, 408, 409, 429, >= 500 |

Retries use exponential backoff.

### Timeouts
| SDK | Default Timeout |
|-----|----------------|
| Python | 60 seconds |
| TypeScript | 60 seconds |
| Go | No default (use context) |
| Java | 60 seconds |
| Ruby | 60 seconds |

### Connection Pooling
| SDK | Pooling |
|-----|---------|
| Python (sync) | httpx connection pooling |
| Python (async) | httpx or aiohttp connection pooling |
| TypeScript | Undici backend connection pooling |
| Go | Standard net/http connection pooling |
| Java | OkHttp connection pooling |
| Ruby | `connection_pool` gem, 99 connections default |

### Pagination
All SDKs support:
- Auto-paginating iterators
- Manual pagination with `hasNextPage()` / `getNextPage()`
- Cursor-based pagination

### Compression
- TypeScript and Ruby support `compression: true` for gzip
- API recommends **disabling** compression (clients are CPU-constrained, not bandwidth-constrained)

---

## 11. LangChain Integration

### Python (langchain-turbopuffer)
- **Package:** `langchain-turbopuffer` on PyPI
- **Version:** 0.2.0 (released February 26, 2026)
- **License:** MIT
- **Repository:** github.com/turbopuffer/langchain-turbopuffer
- **Requirements:** Python 3.10+
- **Status:** Official (previous 0.1.x versions were yanked as "unofficial community version")

#### Installation
```bash
pip install langchain-turbopuffer
```

#### Usage
```python
from langchain_turbopuffer import TurbopufferVectorStore
from langchain_openai import OpenAIEmbeddings
from turbopuffer import Turbopuffer

tpuf = Turbopuffer(
    region="gcp-us-central1",
    api_key=os.environ.get("TURBOPUFFER_API_KEY"),
)

ns = tpuf.namespace("example")

vector_store = TurbopufferVectorStore(
    namespace=ns,
    embedding=OpenAIEmbeddings(),
)
```

### JavaScript (@langchain/turbopuffer)
- **Package:** `@langchain/turbopuffer` on npm
- **Repository:** Part of LangChain.js ecosystem

#### Installation
```bash
npm install @langchain/turbopuffer @turbopuffer/turbopuffer
```

#### Key Classes
- `TurbopufferVectorStore` - Main vector store class
- `TurbopufferAddDocumentOptions` - Document addition configuration
- `TurbopufferDeleteParams` - Deletion parameters
- `TurbopufferParams` - General configuration

#### Methods
- `addDocuments()` - Add documents with embeddings
- `similaritySearch(query, resultLimit)` - Similarity search
- `maxMarginalRelevanceSearch()` - MMR search (optimizes similarity + diversity)
- `delete({ deleteIndex: true })` - Delete all vectors from namespace

#### Limitations
- Only string metadata values currently supported
- Requires external embedding model (e.g., OpenAIEmbeddings)

---

## 12. LlamaIndex Integration

Turbopuffer has a **fork of LlamaIndex** in their GitHub organization (turbopuffer/llama_index), suggesting active development of a LlamaIndex integration. However, as of the research date, there is **no published LlamaIndex integration package** on PyPI or in the official LlamaIndex integrations directory.

The fork likely contains a `TurbopufferVectorStore` implementation compatible with LlamaIndex's `VectorStoreIndex` interface.

---

## 13. Mastra Integration

### Package
- `@mastra/turbopuffer` on npm
- Official integration with the Mastra AI agent framework

### TurbopufferVector Class

#### Constructor Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apiKey` | string | None | Authentication credentials |
| `baseUrl` | string | `https://api.turbopuffer.com` | API endpoint |
| `connectTimeout` | number | 10000 | Connection timeout (ms, Node/Deno only) |
| `connectionIdleTimeout` | number | 60000 | Socket idle timeout (ms) |
| `warmConnections` | number | 0 | Initial connection pool size |
| `compression` | boolean | true | Request/response compression |
| `schemaConfigForIndex` | function | None | Per-index schema definition callback |

#### Methods
| Method | Description |
|--------|-------------|
| `createIndex()` | Create index with dimensions and distance metric |
| `upsert()` | Store vectors with metadata |
| `query()` | Similarity search with topK, filters |
| `listIndexes()` | List all index names |
| `describeIndex()` | Get index metadata (dimensions, count, metric) |
| `deleteIndex()` | Remove entire index |
| `updateVector()` | Modify vector by ID or filter |
| `deleteVector()` | Remove vector by ID |
| `deleteVectors()` | Batch delete by IDs or filters |

#### Distance Metrics
- `cosine`
- `euclidean`
- `dotproduct`

---

## 14. Vectorize Integration

Vectorize (vectorize.io) provides a managed RAG pipeline that outputs to turbopuffer.

### Setup
1. Navigate to Vector Databases in Vectorize dashboard
2. Select "New Vector Database Integration" -> Turbopuffer
3. Provide Name and API Key
4. Specify namespace in pipeline configuration

### Features
- Automatic namespace creation if not exists
- Handles ingestion, chunking, metadata enrichment, embedding
- Supports re-embedding with different models
- End-to-end managed pipeline

---

## 15. Daft Integration

Daft (getdaft.io) provides a distributed DataFrame framework with turbopuffer connector for processing large text datasets and generating embeddings at scale.

### Capabilities
- Process millions of text documents in parallel
- Generate embeddings using state-of-the-art models
- Store embeddings directly in turbopuffer
- Distributed computing for large-scale pipelines

---

## 16. MCP Server (AI Assistant Integration)

### Overview
Turbopuffer provides a Model Context Protocol (MCP) server (beta, launched January 2026) for AI assistant integration.

### Available Tools

#### `turbopuffer_list_namespaces`
Lists all namespaces with dimensions and approximate vector counts.

#### `turbopuffer_vector_search`
Semantic vector search with automatic text-to-embedding conversion.
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Text query (auto-embedded) |
| `namespace` | string | Target namespace |
| `top_k` | number | Results to return (default: 10) |
| `filters` | object | Metadata filtering |

#### `turbopuffer_write_documents`
Write documents with automatic embedding and content-hash deduplication.
| Parameter | Type | Description |
|-----------|------|-------------|
| `namespace` | string | Target namespace |
| `documents` | array | Documents with `page_content` and optional metadata |

### Required Credentials
- `apiKey`: Turbopuffer API key
- `openaiApiKey`: OpenAI API key (for embedding generation)

### Configuration
- `embeddingModel`: OpenAI model (default: `text-embedding-3-large`)
- `includeAttributes`: Default response attributes (default: `page_content, metadata`)

### Installation
Available via deep-links for Cursor and VS Code.

---

## 17. Puffgres (Postgres CDC)

**Repository:** github.com/lucasgelfond/puffgres (archived March 13, 2026)

### What It Does
Change Data Capture pipeline that syncs PostgreSQL changes to turbopuffer using logical replication.

### Architecture
- **CLI** for configuration and setup
- **Runner Service** for mirroring operations
- **Migrations** - Immutable .toml configuration files
- **Transforms** - TypeScript API for row transformation before upserting

### Installation
```bash
brew install puffgres
puffgres init
```

### Technical Stack
- Built on wal2json (PostgreSQL WAL parsing)
- pgwire-replication protocol
- Includes rs-puff (typed Rust client for turbopuffer)
- Rust 86.7%, TypeScript 4.3%

**Status:** Archived as of March 2026.

---

## 18. Turbopuffer GUI (Community Desktop Client)

**Repository:** github.com/MrPeker/turbopuffer-gui

### Features
- Connection management with encrypted API key storage
- Namespace browsing
- Document exploration
- Visual schema design tool
- Complex filter builder
- Aggregation queries with group-by
- Multiple simultaneous connection profiles

### Technology
- Electron + React 19 + TypeScript + Vite
- Tailwind CSS + Radix UI + Zustand
- OS-native encryption for credentials
- Network restricted to *.turbopuffer.com

### Installation
- Pre-built: macOS (.dmg/.zip), Windows (.exe), Linux (.deb/.rpm)
- From source: Node.js 18+, npm 9+

**Status:** Beta, 18 stars, NOT affiliated with turbopuffer.

---

## 19. Benchmark Tool

**Repository:** github.com/turbopuffer/tpuf-benchmark

### Purpose
General purpose benchmarking tool for turbopuffer deployments across workloads.

### Configuration
- TOML configuration files in `benchmarks/website/`
- Example: `vector-1m.toml`
- Supports `--warm-cache` option

### Requirements
- Go 1.25+
- Environment: `TURBOPUFFER_API_KEY`, `TURBOPUFFER_REGION`

### Reference Hardware
- c2-standard-30 instance in GCP us-central1

---

## 20. Import/Export & Data Migration

### Export (Pagination-Based)
No dedicated export endpoint. Export via pagination through the query API:

```python
# Python export pattern
all_rows = []
last_id = None
while True:
    filters = ("id", "Gt", last_id) if last_id else None
    result = ns.query(
        rank_by=("id", "asc"),
        limit=10000,
        filters=filters,
        include_attributes=True,
    )
    if not result.rows:
        break
    all_rows.extend(result.rows)
    last_id = result.rows[-1]["id"]
    if len(result.rows) < 10000:
        break
```

### Import / Migration
- **copy_from_namespace**: Server-side namespace copy (efficient, no client data transfer)
  - Basic: `"copy_from_namespace": "source-ns"`
  - Advanced: `{"source_namespace": "ns", "source_api_key": "key", "source_region": "region"}`
  - Cross-region within same cloud provider
  - Cross-organization with source_api_key
  - Billed at up to 75% write discount

### Backup Strategy
- No automated backups
- Use `copy_from_namespace` for cross-region backup
- Backup namespaces are fully writable and queryable
- Scheduled backup scripts (Python/JS/Go/Java examples in docs)
- Typical pattern: daily/weekly copies with retention policy

---

## 21. Monitoring & Observability

### Built-in Metrics (per-query response)
Every query response includes `performance` and `billing` objects:

```json
{
  "performance": {
    "cache_hit_ratio": 0.95,
    "cache_temperature": "hot|warm|cold",
    "server_total_ms": 12,
    "query_execution_ms": 8,
    "exhaustive_search_count": 0,
    "approx_namespace_size": 1000000
  },
  "billing": {
    "billable_logical_bytes_queried": 1024,
    "billable_logical_bytes_returned": 256
  }
}
```

### Write Response Metrics
```json
{
  "billing": {...},
  "performance": {...}
}
```

### Dashboard
- Turbopuffer dashboard (mentioned as "major dashboard improvements" planned)
- SOC 2 trust center available

### External Monitoring
- No native OpenTelemetry, Prometheus, or Datadog integration documented
- No webhook/event system for monitoring
- Clients can build monitoring from per-response metrics

### Recall Monitoring
- Automatic recall measurement on 1% of live traffic
- Targets 90-95% recall@10
- Debug endpoint: `POST /v1/namespaces/:namespace/_debug/recall`

---

## 22. Webhooks/Events

Turbopuffer does **NOT** provide:
- Webhooks
- Event streams
- Change notifications
- Change Data Capture (CDC)

The only CDC-like tool was **puffgres** (Postgres->turbopuffer, now archived). For change detection, applications must poll or maintain their own event system.

---

## 23. Embedding Model Integrations

Turbopuffer itself does **NOT generate embeddings**. It stores and searches pre-computed vectors. Embedding generation is the client's responsibility.

### Commonly Used With:
| Provider | Models | Integration Pattern |
|----------|--------|--------------------|
| OpenAI | text-embedding-3-large, text-embedding-3-small, text-embedding-ada-002 | Generate embeddings client-side, send vectors to turbopuffer |
| Cohere | embed-english-v3.0, embed-multilingual-v3.0 | Same pattern |
| Voyage AI | voyage-large-2, voyage-code-2 | Same pattern |
| Google | text-embedding-004 | Same pattern |
| Local models | sentence-transformers, INSTRUCTOR, etc. | Same pattern |

### MCP Server Auto-Embedding
The MCP server is the **only** turbopuffer component that auto-generates embeddings (using OpenAI).

### Supported Vector Dimensions
- Maximum: 10,752 dimensions
- Encoding: f32 (default) or f16 (50% storage savings)

---

## 24. Re-Ranker Integrations

Turbopuffer does not include built-in re-ranking. Re-ranking is done client-side after retrieval. The hybrid search guide recommends:

| Re-Ranker | Usage Pattern |
|-----------|--------------|
| Cohere | `cohere.rerank(model="rerank-english-v3.0", query=q, documents=docs)` |
| ZeroEntropy | API-based re-ranking after turbopuffer retrieval |
| MixedBread | API-based re-ranking |
| Voyage AI | `voyageai.rerank(model="rerank-2", query=q, documents=docs)` |

### Hybrid Search + Re-Rank Pipeline
```
User Query -> Query Rewriting (optional LLM) ->
  Multi-Query (vector ANN + BM25 FTS) ->
  Reciprocal Rank Fusion ->
  Re-Ranking (Cohere/ZeroEntropy/Voyage) ->
  Final Results
```

---

## 25. Regions & Infrastructure

### GCP Regions (7)
| Region | Location | Endpoint |
|--------|----------|----------|
| gcp-us-central1 | Iowa | https://gcp-us-central1.turbopuffer.com |
| gcp-us-west1 | Oregon | https://gcp-us-west1.turbopuffer.com |
| gcp-us-east4 | N. Virginia | https://gcp-us-east4.turbopuffer.com |
| gcp-northamerica-northeast2 | Toronto | https://gcp-northamerica-northeast2.turbopuffer.com |
| gcp-europe-west3 | Frankfurt | https://gcp-europe-west3.turbopuffer.com |
| gcp-asia-southeast1 | Singapore | https://gcp-asia-southeast1.turbopuffer.com |
| gcp-asia-northeast3 | Seoul | https://gcp-asia-northeast3.turbopuffer.com |

### AWS Regions (9)
| Region | Location | Endpoint |
|--------|----------|----------|
| aws-us-east-1 | N. Virginia | https://aws-us-east-1.turbopuffer.com |
| aws-us-east-2 | Ohio | https://aws-us-east-2.turbopuffer.com |
| aws-us-west-2 | Oregon | https://aws-us-west-2.turbopuffer.com |
| aws-ca-central-1 | Montreal | https://aws-ca-central-1.turbopuffer.com |
| aws-eu-central-1 | Frankfurt | https://aws-eu-central-1.turbopuffer.com |
| aws-eu-west-1 | Ireland | https://aws-eu-west-1.turbopuffer.com |
| aws-eu-west-2 | London | https://aws-eu-west-2.turbopuffer.com |
| aws-ap-south-1 | Mumbai | https://aws-ap-south-1.turbopuffer.com |
| aws-ap-southeast-2 | Sydney | https://aws-ap-southeast-2.turbopuffer.com |

### Additional Options
- Azure: Available for "Deploy in your VPC" (no public regions)
- Dedicated clusters: Available upon request
- BYOC (Bring Your Own Cloud): Enterprise plan

### Private Networking
- AWS: PrivateLink (`https://privatelink.[region].turbopuffer.com`)
- GCP: Private Service Connect (`https://[endpoint].psc.[region].turbopuffer.com`)
- Enterprise plan only, no usage-based fees
- Cross-cloud private connections NOT supported
- Optional enforcement to restrict all API access to private endpoints

---

## 26. Security & Compliance

| Feature | Details |
|---------|---------|
| Encryption in Transit | TLS 1.2+ |
| Encryption at Rest | AES-256 |
| CMEK | Per-namespace customer-managed keys (GCP/AWS KMS, Enterprise) |
| SOC 2 Type 2 | Audited annually (2025 report available) |
| HIPAA | BAA available (Scale/Enterprise plans) |
| GDPR/CCPA | DPA available to all customers |
| SSO | Dashboard SSO (Scale/Enterprise plans) |
| Private Networking | PrivateLink / Private Service Connect (Enterprise) |
| FIPS | Compliant AWS endpoints for BYOC |
| Vulnerability Disclosure | Formal policy for security researchers |

---

## 27. Pricing Structure

### Plans
| Plan | Minimum | Deployment | Key Features |
|------|---------|------------|--------------|
| Launch | $64/month | Multi-Tenant | All DB features, SOC2, GDPR DPA |
| Scale | $256/month | Multi-Tenant | + HIPAA BAA, SSO, Private Slack |
| Enterprise | $4,096+/month (35% premium) | Multi-Tenant, Single-Tenant, BYOC | + CMEK, Private Networking, 24/7 SLA, 99.95% uptime |

### Usage-Based Pricing
- **Storage:** Billed on logical bytes ingested (not physical overhead)
- **Queries:** Billed as sum of data queried + data returned (tiered discounts at 32GB+, 128GB+)
- **Writes:** Minimum 10KB per write; batch discount up to 50% (`discount = min((log10(KB) - 1) * 0.2, 0.5)`)
- **Vectors:** f32 = 4 bytes/dim, f16 = 2 bytes/dim for storage
- **Attributes:** Non-filterable attributes receive 50% discount
- **No free tier** (planned for future)

---

## 28. OpenAPI Specification

**Repository:** github.com/turbopuffer/turbopuffer-openapi

### Status
- Primarily intended for internal use
- May contain nonstandard features
- Subject to breaking changes
- MIT licensed

### Complete Endpoint List from OpenAPI Spec
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/namespaces` | List namespaces |
| GET | `/v1/namespaces/{namespace}/schema` | Get namespace schema |
| POST | `/v1/namespaces/{namespace}/schema` | Update namespace schema |
| GET | `/v1/namespaces/{namespace}/metadata` | Get namespace metadata |
| GET | `/v1/namespaces/{namespace}/hint_cache_warm` | Warm cache |
| POST | `/v1/namespaces/{namespace}/_debug/recall` | Recall testing |
| POST | `/v2/namespaces/{namespace}` | Write documents |
| DELETE | `/v2/namespaces/{namespace}` | Delete namespace |
| POST | `/v2/namespaces/{namespace}/query` | Query documents |
| POST | `/v2/namespaces/{namespace}/query` (multiQuery) | Multi-query |
| POST | `/v2/namespaces/{namespace}/explain_query` | Explain query plan |

### SDK Generation
All official SDKs (Python, TypeScript, Go, Java, Ruby) are generated from this spec via Stainless. CI/CD via GitHub Actions auto-rebuilds SDKs on spec changes.

---

## 29. Roadmap & Changelog Highlights

### Planned Features (as of March 2026)
- Faster & smarter cache warming
- Major dashboard improvements
- Query and indexing performance improvements
- Full-text search highlighting and search-as-you-type
- More aggregate functions (distinct, min, max)
- Late interaction support
- Nested attributes
- Namespace branching
- Namespace cache pinning

### Key Historical Milestones
| Date | Feature |
|------|---------|
| May 2025 | General availability, v2 query API |
| June 2025 | Conditional writes, Multi-query API, Python async, Java GA, Go GA |
| July 2025 | Private Service Connect/PrivateLink, Ruby GA |
| September 2025 | ANN v3 (100B+ vectors), SOC 2 Type 2 |
| October 2025 | Read replicas, patch_by_filter |
| November 2025 | FTS v2 beta (20x faster) |
| January 2026 | FTS v2 GA, MCP Server beta |
| February 2026 | Query pricing reduced up to 94%, regex index, multiple vectors per document (beta) |

---

## 30. Implications for bigRAG

### SDK Strategy for bigRAG
bigRAG should offer SDKs in the same 5 languages as turbopuffer (Python, TypeScript, Go, Java, Ruby), plus Rust as a first-class citizen since bigRAG itself is Rust-based. Key considerations:

1. **API Compatibility:** bigRAG's REST API should aim for wire-level compatibility with turbopuffer's v2 API where possible, enabling easy migration.

2. **Filter Syntax:** turbopuffer's tuple-based filter syntax (`["field", "Eq", "value"]`) is the de-facto standard. bigRAG should support an identical or compatible format.

3. **Ranking Methods:** The `rank_by` array syntax for ANN, BM25, and composite ranking (Sum, Product, Max, Saturate, Decay, Dist) should be studied for compatibility.

4. **Schema Model:** turbopuffer's schema with `filterable`, `full_text_search`, and `regex` flags per attribute is a good model.

5. **Authentication:** Simple Bearer token auth. No complex RBAC needed initially.

6. **LangChain/LlamaIndex Integration:** These are the most important framework integrations. bigRAG should provide `bigRAGVectorStore` for both LangChain and LlamaIndex.

7. **No Built-in Embeddings:** turbopuffer deliberately does NOT generate embeddings. This is the standard pattern for vector databases - bigRAG should follow the same approach.

8. **Namespace Model:** Unlimited namespaces with implicit creation on first write is the expected UX.

9. **Multi-Query:** The multi-query API (up to 16 subqueries) is critical for hybrid search patterns (vector + BM25 in one call).

10. **Export Approach:** Pagination-based export via query API (no dedicated export endpoint) is the standard pattern.

11. **Self-Hosted Advantage:** turbopuffer's lack of a free tier and open-source option is bigRAG's key differentiator. bigRAG should offer Docker/K8s deployment with no minimum spend.

12. **MCP Server:** Providing an MCP server for AI assistant integration is becoming table-stakes. bigRAG should include one.

### API Surface Gap Analysis
turbopuffer features bigRAG should prioritize:
- v2 Write API with upsert_rows, patch_rows, deletes, delete_by_filter, patch_by_filter
- v2 Query API with ANN, kNN, BM25, filters, aggregations, multi-query
- Namespace metadata, schema management, list/delete namespaces
- Recall testing endpoint
- Cache warming hint
- Query explain for debugging
- Conditional writes
- copy_from_namespace for migration/backup
