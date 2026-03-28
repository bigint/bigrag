# @bigrag/client

TypeScript client for [bigRAG](https://github.com/yoginth/bigrag) — a vector + full-text search database.

## Installation

```bash
npm install @bigrag/client
```

## Quick Start

```typescript
import { BigRAG } from "@bigrag/client";

const client = new BigRAG({
  apiKey: "your-api-key",
  baseUrl: "http://localhost:8080",
});

// Check server health
const health = await client.health();

// Create a namespace handle
const ns = client.namespace("my-collection");

// Upsert rows with vectors and attributes
await ns.upsert(
  [
    { id: 1, vector: [0.1, 0.2, 0.3], title: "First document" },
    { id: 2, vector: [0.4, 0.5, 0.6], title: "Second document" },
  ],
  { distanceMetric: "cosine_distance" },
);

// Query by vector similarity
const results = await ns.query({
  rankBy: ["vector", "ANN", [0.1, 0.2, 0.3]],
  topK: 10,
  includeAttributes: true,
});

console.log(results.rows);

// Query with filters
const filtered = await ns.query({
  rankBy: ["vector", "ANN", [0.1, 0.2, 0.3]],
  topK: 5,
  filters: ["title", "Eq", "First document"],
  includeAttributes: true,
});

// Full-text search with BM25
const textResults = await ns.query({
  rankBy: ["bm25", "title", "document"],
  topK: 10,
  includeAttributes: true,
});

// Delete rows by ID
await ns.delete([1, 2]);

// Delete entire namespace
await ns.deleteAll();
```

## Configuration

| Option       | Default                  | Description                           |
| ------------ | ------------------------ | ------------------------------------- |
| `apiKey`     | `BIGRAG_API_KEY` env var | API key for authentication            |
| `baseUrl`    | `http://localhost:8080`  | bigRAG server URL                     |
| `timeout`    | `30000`                  | Request timeout in milliseconds       |
| `maxRetries` | `3`                      | Max retries on transient failures     |

## Error Handling

```typescript
import { BigRAG, NotFoundError, RateLimitError } from "@bigrag/client";

try {
  await ns.metadata();
} catch (err) {
  if (err instanceof NotFoundError) {
    console.log("Namespace does not exist");
  } else if (err instanceof RateLimitError) {
    console.log("Rate limited, try again later");
  }
}
```

## License

Apache-2.0
