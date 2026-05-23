# bigRAG Admin UI

A Vite + TanStack Router admin console for bigRAG. It manages collections,
documents, live ingestion status, chat with citations, S3/R2 sources, access
logs, and API/MCP keys.

## Running

```bash
pnpm install
pnpm dev:app
```

Open http://localhost:3000. On first run the `/setup` page lets you create the
initial admin account.

The SPA calls the FastAPI server directly. In development, either leave the app
default at `http://localhost:4000` or set:

```bash
VITE_BIGRAG_URL=http://localhost:4000
```

The API must allow the app origin:

```bash
BIGRAG_CORS_ORIGINS='["http://localhost:3000"]'
```

## Stack

- Vite · TanStack Router · React 19 · TypeScript
- Tailwind CSS v4 with black/white admin styling
- Base UI for accessible primitives
- TanStack Query + Ky for data · Sonner for toasts

Production containers serve static `dist` assets with Nginx. Set `BIGRAG_URL`
on the app container to write runtime `config.js`; build-time
`VITE_BIGRAG_URL` remains supported for non-container static hosting.
