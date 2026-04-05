import { describe, it, expect } from "vitest";
import { BigRAG } from "../src/client.js";
import { createMockClient } from "./helpers.js";

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------

describe("BigRAG constructor", () => {
  it("uses default baseUrl", () => {
    const { client } = createMockClient();
    expect(client.baseUrl).toBe("http://localhost:6100");
  });

  it("strips trailing slashes from baseUrl", () => {
    const { client } = createMockClient({}, 200, {
      baseUrl: "http://example.com///",
    });
    expect(client.baseUrl).toBe("http://example.com");
  });

  it("reads apiKey from options", () => {
    const { client } = createMockClient({}, 200, { apiKey: "my-key" });
    expect(client.apiKey).toBe("my-key");
  });

  it("defaults maxRetries and timeout", () => {
    const client = new BigRAG({ fetch: globalThis.fetch });
    expect(client.maxRetries).toBe(2);
    expect(client.timeout).toBe(120_000);
  });
});

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

describe("health", () => {
  it("GET /health", async () => {
    const { client, calls } = createMockClient({ status: "ok", version: "0.0.2" });
    const result = await client.health();
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/health");
    expect(result.status).toBe("ok");
  });

  it("GET /health/ready", async () => {
    const body = { status: "ok", version: "0.0.2", postgres: true, milvus: true, redis: true };
    const { client, calls } = createMockClient(body);
    const result = await client.readiness();
    expect(calls[0].url).toContain("/health/ready");
    expect(result.postgres).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Collections
// ---------------------------------------------------------------------------

describe("collections", () => {
  it("POST /v1/collections", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.createCollection({ name: "docs" });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/collections");
    expect(JSON.parse(calls[0].body!).name).toBe("docs");
  });

  it("GET /v1/collections", async () => {
    const { client, calls } = createMockClient({ collections: [] });
    await client.listCollections();
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/v1/collections");
  });

  it("GET /v1/collections/{name}", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.getCollection("docs");
    expect(calls[0].url).toContain("/v1/collections/docs");
  });

  it("PUT /v1/collections/{name}", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.updateCollection("docs", { description: "updated" });
    expect(calls[0].method).toBe("PUT");
    expect(JSON.parse(calls[0].body!).description).toBe("updated");
  });

  it("DELETE /v1/collections/{name}", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.deleteCollection("docs");
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toContain("/v1/collections/docs");
  });

  it("encodes special characters in collection name", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "my collection" });
    await client.getCollection("my collection");
    expect(calls[0].url).toContain("my%20collection");
  });

  it("sends default_top_k in create body", async () => {
    const { client, calls } = createMockClient({ id: "1" });
    await client.createCollection({ name: "docs", default_top_k: 20, default_search_mode: "hybrid" });
    const body = JSON.parse(calls[0].body!);
    expect(body.default_top_k).toBe(20);
    expect(body.default_search_mode).toBe("hybrid");
  });
});

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

describe("documents", () => {
  it("GET /v1/collections/{name}/documents", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.listDocuments("docs");
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/v1/collections/docs/documents");
  });

  it("listDocuments with query params", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.listDocuments("docs", { status: "ready", limit: 10, offset: 5 });
    expect(calls[0].url).toContain("status=ready");
    expect(calls[0].url).toContain("limit=10");
    expect(calls[0].url).toContain("offset=5");
  });

  it("GET /v1/collections/{name}/documents/{id}", async () => {
    const { client, calls } = createMockClient({ id: "doc1" });
    await client.getDocument("docs", "doc1");
    expect(calls[0].url).toContain("/v1/collections/docs/documents/doc1");
  });

  it("DELETE /v1/collections/{name}/documents/{id}", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.deleteDocument("docs", "doc1");
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toContain("/v1/collections/docs/documents/doc1");
  });

  it("POST .../documents/{id}/reprocess", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.reprocessDocument("docs", "doc1");
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/documents/doc1/reprocess");
  });

  it("GET .../documents/{id}/chunks", async () => {
    const { client, calls } = createMockClient({ chunks: [], total: 0 });
    await client.getDocumentChunks("docs", "doc1");
    expect(calls[0].url).toContain("/documents/doc1/chunks");
  });

  it("getDocumentFileUrl includes token when apiKey set", () => {
    const { client } = createMockClient({}, 200, { apiKey: "key123" });
    const url = client.getDocumentFileUrl("docs", "doc1");
    expect(url).toContain("/documents/doc1/file");
    expect(url).toContain("token=key123");
  });

  it("getDocumentFileUrl omits token when no apiKey", () => {
    const { client } = createMockClient({}, 200, { apiKey: "" });
    const url = client.getDocumentFileUrl("docs", "doc1");
    expect(url).toContain("/documents/doc1/file");
    expect(url).not.toContain("token=");
  });
});

// ---------------------------------------------------------------------------
// Batch operations
// ---------------------------------------------------------------------------

describe("batch operations", () => {
  it("POST .../documents/batch/status", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.batchGetStatus("docs", ["id1", "id2"]);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/documents/batch/status");
    expect(JSON.parse(calls[0].body!).document_ids).toEqual(["id1", "id2"]);
  });

  it("POST .../documents/batch/delete", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 2, errors: [] });
    await client.batchDeleteDocuments("docs", ["id1", "id2"]);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/documents/batch/delete");
    expect(JSON.parse(calls[0].body!).document_ids).toEqual(["id1", "id2"]);
  });
});

// ---------------------------------------------------------------------------
// Query
// ---------------------------------------------------------------------------

describe("query", () => {
  it("POST /v1/collections/{name}/query", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    await client.query("docs", { query: "hello", top_k: 5 });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/collections/docs/query");
    const body = JSON.parse(calls[0].body!);
    expect(body.query).toBe("hello");
    expect(body.top_k).toBe(5);
  });

  it("POST /v1/query (multi-collection)", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    await client.multiQuery({ query: "test", collections: ["a", "b"] });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/query");
    expect(JSON.parse(calls[0].body!).collections).toEqual(["a", "b"]);
  });

  it("POST /v1/batch/query", async () => {
    const { client, calls } = createMockClient({ results: [] });
    await client.batchQuery({ queries: [{ collection: "docs", query: "test" }] });
    expect(calls[0].url).toContain("/v1/batch/query");
    expect(JSON.parse(calls[0].body!).queries).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Vectors
// ---------------------------------------------------------------------------

describe("vectors", () => {
  it("POST .../vectors/upsert", async () => {
    const { client, calls } = createMockClient({ status: "ok", upserted: 1 });
    await client.upsertVectors("docs", [
      { id: "v1", embedding: [0.1, 0.2], text: "hello" },
    ]);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/vectors/upsert");
    const body = JSON.parse(calls[0].body!);
    expect(body.vectors).toHaveLength(1);
    expect(body.vectors[0].id).toBe("v1");
  });

  it("POST .../vectors/delete", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 2 });
    await client.deleteVectors("docs", ["v1", "v2"]);
    expect(calls[0].url).toContain("/vectors/delete");
    expect(JSON.parse(calls[0].body!).ids).toEqual(["v1", "v2"]);
  });
});

// ---------------------------------------------------------------------------
// Stats & Embeddings
// ---------------------------------------------------------------------------

describe("stats and embeddings", () => {
  it("GET /v1/stats", async () => {
    const { client, calls } = createMockClient({ collections: 5 });
    await client.getStats();
    expect(calls[0].url).toContain("/v1/stats");
  });

  it("GET /v1/embeddings/models", async () => {
    const { client, calls } = createMockClient({ models: [] });
    await client.listEmbeddingModels();
    expect(calls[0].url).toContain("/v1/embeddings/models");
  });

  it("GET /v1/collections/{name}/analytics", async () => {
    const { client, calls } = createMockClient({ collection: "docs" });
    await client.getAnalytics("docs");
    expect(calls[0].url).toContain("/v1/collections/docs/analytics");
  });
});

// ---------------------------------------------------------------------------
// Webhooks
// ---------------------------------------------------------------------------

describe("webhooks", () => {
  it("POST /v1/admin/webhooks", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.createWebhook({
      url: "https://example.com/hook",
      events: ["document.ready"],
    });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/admin/webhooks");
    expect(JSON.parse(calls[0].body!).url).toBe("https://example.com/hook");
  });

  it("GET /v1/admin/webhooks", async () => {
    const { client, calls } = createMockClient({ webhooks: [] });
    await client.listWebhooks();
    expect(calls[0].url).toContain("/v1/admin/webhooks");
  });

  it("GET /v1/admin/webhooks/{id}", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.getWebhook("wh1");
    expect(calls[0].url).toContain("/v1/admin/webhooks/wh1");
  });

  it("PUT /v1/admin/webhooks/{id}", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.updateWebhook("wh1", { description: "updated" });
    expect(calls[0].method).toBe("PUT");
    expect(JSON.parse(calls[0].body!).description).toBe("updated");
  });

  it("DELETE /v1/admin/webhooks/{id}", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.deleteWebhook("wh1");
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toContain("/v1/admin/webhooks/wh1");
  });

  it("GET .../webhooks/{id}/deliveries with pagination", async () => {
    const { client, calls } = createMockClient({ deliveries: [], total: 0 });
    await client.listWebhookDeliveries("wh1", { limit: 10, offset: 20 });
    expect(calls[0].url).toContain("/webhooks/wh1/deliveries");
    expect(calls[0].url).toContain("limit=10");
    expect(calls[0].url).toContain("offset=20");
  });

  it("POST .../webhooks/{id}/test", async () => {
    const { client, calls } = createMockClient({ status: "delivered" });
    await client.testWebhook("wh1");
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/webhooks/wh1/test");
  });
});

// ---------------------------------------------------------------------------
// Auth headers
// ---------------------------------------------------------------------------

describe("auth headers", () => {
  it("sends Bearer token when apiKey is set", async () => {
    const { client, calls } = createMockClient({}, 200, { apiKey: "secret" });
    await client.health();
    expect(calls[0].headers["Authorization"]).toBe("Bearer secret");
  });

  it("omits Authorization when apiKey is empty", async () => {
    const { client, calls } = createMockClient({}, 200, { apiKey: "" });
    await client.health();
    expect(calls[0].headers["Authorization"]).toBeUndefined();
  });

  it("sends Content-Type for JSON requests", async () => {
    const { client, calls } = createMockClient({ id: "1" });
    await client.createCollection({ name: "docs" });
    expect(calls[0].headers["Content-Type"]).toBe("application/json");
  });

  it("does not send Content-Type for GET requests", async () => {
    const { client, calls } = createMockClient({ collections: [] });
    await client.listCollections();
    expect(calls[0].headers["Content-Type"]).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// CollectionClient (scoped)
// ---------------------------------------------------------------------------

describe("CollectionClient", () => {
  it("delegates query with collection name", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    const col = client.collection("mydata");
    await col.query({ query: "test" });
    expect(calls[0].url).toContain("/v1/collections/mydata/query");
  });

  it("delegates listDocuments", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    const col = client.collection("mydata");
    await col.listDocuments({ limit: 5 });
    expect(calls[0].url).toContain("/v1/collections/mydata/documents");
    expect(calls[0].url).toContain("limit=5");
  });

  it("delegates getDocument", async () => {
    const { client, calls } = createMockClient({ id: "doc1" });
    const col = client.collection("mydata");
    await col.getDocument("doc1");
    expect(calls[0].url).toContain("/v1/collections/mydata/documents/doc1");
  });

  it("delegates deleteDocument", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    const col = client.collection("mydata");
    await col.deleteDocument("doc1");
    expect(calls[0].method).toBe("DELETE");
  });

  it("delegates reprocessDocument", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    const col = client.collection("mydata");
    await col.reprocessDocument("doc1");
    expect(calls[0].url).toContain("/documents/doc1/reprocess");
  });

  it("delegates batchGetStatus", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    const col = client.collection("mydata");
    await col.batchGetStatus(["id1"]);
    expect(calls[0].url).toContain("/documents/batch/status");
  });

  it("delegates batchDelete", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 1, errors: [] });
    const col = client.collection("mydata");
    await col.batchDelete(["id1"]);
    expect(calls[0].url).toContain("/documents/batch/delete");
  });

  it("delegates analytics", async () => {
    const { client, calls } = createMockClient({ collection: "mydata" });
    const col = client.collection("mydata");
    await col.analytics();
    expect(calls[0].url).toContain("/v1/collections/mydata/analytics");
  });

  it("delegates getDocumentChunks", async () => {
    const { client, calls } = createMockClient({ chunks: [], total: 0 });
    const col = client.collection("mydata");
    await col.getDocumentChunks("doc1");
    expect(calls[0].url).toContain("/documents/doc1/chunks");
  });
});
