# @bigrag/client

TypeScript client for [bigRAG](https://github.com/yoginth/bigrag) — a self-hostable RAG platform.

> **Note**: This SDK is being updated to match the new collections-based API. Some methods may not yet be implemented.

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

const health = await client.health();
```

## Configuration

| Option       | Default                  | Description                           |
| ------------ | ------------------------ | ------------------------------------- |
| `apiKey`     | `BIGRAG_API_KEY` env var | API key for authentication            |
| `baseUrl`    | `http://localhost:8080`  | bigRAG server URL                     |
| `timeout`    | `30000`                  | Request timeout in milliseconds       |
| `maxRetries` | `3`                      | Max retries on transient failures     |

## License

Apache-2.0
