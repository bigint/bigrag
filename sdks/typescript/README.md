# @bigrag/client

TypeScript client for [bigRAG](https://github.com/yoginth/bigrag) — a self-hostable RAG platform.

Zero dependencies. Works in Node.js 18+, browsers, Deno, Bun, and edge runtimes.

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

// List collections
const { collections } = await client.listCollections();

// Upload a document
const doc = await client.uploadDocument("my_collection", file);

// Query
const results = await client.query("my_collection", {
  query: "What is RAG?",
  top_k: 5,
});

// Stream document processing progress
for await (const event of client.streamDocumentProgress("my_collection", doc.id)) {
  console.log(event.step, event.progress);
  if (event.status === "complete") break;
}
```

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `apiKey` | `BIGRAG_API_KEY` env var | API key or session token |
| `baseUrl` | `http://localhost:8080` | bigRAG server URL |
| `timeout` | `120000` | Request timeout in milliseconds |
| `maxRetries` | `2` | Max retries on 5xx, 429, and network errors |
| `fetch` | `globalThis.fetch` | Custom fetch implementation |

## Error Handling

```typescript
import { BigRAG, AuthenticationError, NotFoundError } from "@bigrag/client";

try {
  await client.getCollection("missing");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.log("Collection not found");
  } else if (err instanceof AuthenticationError) {
    console.log("Invalid credentials");
  }
}
```

## Publishing

The SDK is published to npm automatically via GitHub Actions when a release is created with a tag matching `sdk-v*` (e.g., `sdk-v0.1.0`).

To publish manually:

```bash
cd sdks/typescript
npm run build
npm publish --access public
```

### Release steps

1. Update `version` in `package.json`
2. Commit: `git commit -m "chore: bump SDK to vX.Y.Z"`
3. Create a GitHub release with tag `sdk-vX.Y.Z`
4. The workflow builds and publishes to npm automatically

Requires an `NPM_TOKEN` secret in the repository settings.

## License

Apache-2.0
