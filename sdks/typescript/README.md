# @rag.computer/client

TypeScript client for [rag.computer](https://github.com/yoginth/rag-computer) — a self-hostable RAG platform.

Zero dependencies. Works in Node.js 18+, browsers, Deno, Bun, and edge runtimes.

## Installation

```bash
npm install @rag.computer/client
```

## Quick Start

```typescript
import { RagComputer } from "@rag.computer/client";

const client = new RagComputer({
  apiKey: "your-api-key",
  baseUrl: "http://localhost:4000",
});

// List collections
const { collections } = await client.collections.list();

// Upload a document
const doc = await client.documents.upload("my_collection", file);

// Query
const results = await client.queries.query("my_collection", {
  query: "What is RAG?",
  top_k: 5,
});

// Poll document processing status
let current = doc;
while (current.status === "pending" || current.status === "processing") {
  await new Promise((resolve) => setTimeout(resolve, 2000));
  current = await client.documents.get("my_collection", doc.id);
  console.log(current.progress?.message ?? current.status);
}
```

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `apiKey` | `RAG_COMPUTER_API_KEY` env var | API key or session token |
| `baseUrl` | `http://localhost:4000` | rag.computer server URL |
| `timeout` | `120000` | Request timeout in milliseconds |
| `maxRetries` | `2` | Max retries on 5xx, infrastructure 429 responses, and network errors |
| `fetch` | `globalThis.fetch` | Custom fetch implementation |

## Namespaces

- `client.collections` for collection CRUD, stats, re-embedding, analytics, and event streams.
- `client.documents` for uploads, batch operations, file URLs, and status polling.
- `client.queries` for single, multi-collection, and batch retrieval queries.
- `client.chat` for generated answers, streaming, and conversation CRUD.
- `client.vectors` for raw vector upsert and delete.
- `client.webhooks` for webhook management and delivery replay.
- `client.auth` for setup, login, identity, password, and preferences.
- `client.admin` for users, API keys, access logs, audit logs, connectors, embedding presets, and MCP server keys.
- `client.connectors.google` for Google Drive account, file browsing, sources, and sync jobs.
- `client.evaluations` for golden-set retrieval evaluations.

## Error Handling

```typescript
import { RagComputer, AuthenticationError, NotFoundError } from "@rag.computer/client";

try {
  await client.collections.get("missing");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.log("Collection not found");
  } else if (err instanceof AuthenticationError) {
    console.log("Invalid credentials");
  }
}
```

## License

MIT
