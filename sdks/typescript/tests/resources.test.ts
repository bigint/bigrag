import { describe, expect, it } from "vitest";
import { BigRAG } from "../src/client.js";
import { BigRAGCore } from "../src/core.js";
import {
  CollectionsResource,
  DocumentsResource,
  QueryResource,
  VectorsResource,
  WebhooksResource,
} from "../src/resources/index.js";
import { createMockClient } from "./helpers.js";

// ---------------------------------------------------------------------------
// Resource namespaces exist on the client
// ---------------------------------------------------------------------------

describe("resource namespace wiring", () => {
  it("client exposes all resource namespaces", () => {
    const { client } = createMockClient();
    expect(client.collections).toBeInstanceOf(CollectionsResource);
    expect(client.documents).toBeInstanceOf(DocumentsResource);
    expect(client.queries).toBeInstanceOf(QueryResource);
    expect(client.vectors).toBeInstanceOf(VectorsResource);
    expect(client.webhooks).toBeInstanceOf(WebhooksResource);
  });

  it("BigRAG extends BigRAGCore", () => {
    const { client } = createMockClient();
    expect(client).toBeInstanceOf(BigRAGCore);
  });
});

// ---------------------------------------------------------------------------
// CollectionsResource
// ---------------------------------------------------------------------------

describe("CollectionsResource", () => {
  it("list() calls GET /v1/collections", async () => {
    const { client, calls } = createMockClient({ collections: [], total: 0 });
    await client.collections.list();
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/v1/collections");
  });

  it("list() passes query params", async () => {
    const { client, calls } = createMockClient({ collections: [], total: 0 });
    await client.collections.list({ name: "test", limit: 5, offset: 10 });
    expect(calls[0].url).toContain("name=test");
    expect(calls[0].url).toContain("limit=5");
    expect(calls[0].url).toContain("offset=10");
  });

  it("get() calls GET /v1/collections/{name}", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.collections.get("docs");
    expect(calls[0].url).toContain("/v1/collections/docs");
  });

  it("create() calls POST /v1/collections", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.collections.create({ name: "docs" });
    expect(calls[0].method).toBe("POST");
    expect(JSON.parse(calls[0].body!).name).toBe("docs");
  });

  it("update() calls PUT /v1/collections/{name}", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.collections.update("docs", { description: "updated" });
    expect(calls[0].method).toBe("PUT");
    expect(JSON.parse(calls[0].body!).description).toBe("updated");
  });

  it("delete() calls DELETE /v1/collections/{name}", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.collections.delete("docs");
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toContain("/v1/collections/docs");
  });

  it("stats() calls GET /v1/collections/{name}/stats", async () => {
    const { client, calls } = createMockClient({ collection: "docs" });
    await client.collections.stats("docs");
    expect(calls[0].url).toContain("/v1/collections/docs/stats");
  });

  it("encodes special characters in name", async () => {
    const { client, calls } = createMockClient({ id: "1" });
    await client.collections.get("my collection");
    expect(calls[0].url).toContain("my%20collection");
  });
});

// ---------------------------------------------------------------------------
// DocumentsResource
// ---------------------------------------------------------------------------

describe("DocumentsResource", () => {
  it("list() calls GET /v1/collections/{name}/documents", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.documents.list("docs");
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/v1/collections/docs/documents");
  });

  it("list() with query params", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.documents.list("docs", { status: "ready", limit: 10, offset: 5 });
    expect(calls[0].url).toContain("status=ready");
    expect(calls[0].url).toContain("limit=10");
    expect(calls[0].url).toContain("offset=5");
  });

  it("get() calls GET /v1/collections/{name}/documents/{id}", async () => {
    const { client, calls } = createMockClient({ id: "doc1" });
    await client.documents.get("docs", "doc1");
    expect(calls[0].url).toContain("/v1/collections/docs/documents/doc1");
  });

  it("delete() calls DELETE /v1/collections/{name}/documents/{id}", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.documents.delete("docs", "doc1");
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toContain("/v1/collections/docs/documents/doc1");
  });

  it("reprocess() calls POST .../documents/{id}/reprocess", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.documents.reprocess("docs", "doc1");
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/documents/doc1/reprocess");
  });

  it("getChunks() calls GET .../documents/{id}/chunks", async () => {
    const { client, calls } = createMockClient({ chunks: [], total: 0 });
    await client.documents.getChunks("docs", "doc1");
    expect(calls[0].url).toContain("/documents/doc1/chunks");
  });

  it("getFileUrl() includes token when apiKey set", () => {
    const { client } = createMockClient({}, 200, { apiKey: "key123" });
    const url = client.documents.getFileUrl("docs", "doc1");
    expect(url).toContain("/documents/doc1/file");
    expect(url).toContain("token=key123");
  });

  it("getFileUrl() omits token when no apiKey", () => {
    const { client } = createMockClient({}, 200, { apiKey: "" });
    const url = client.documents.getFileUrl("docs", "doc1");
    expect(url).toContain("/documents/doc1/file");
    expect(url).not.toContain("token=");
  });

  it("batchGetStatus() calls POST .../documents/batch/status", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.documents.batchGetStatus("docs", ["id1", "id2"]);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/documents/batch/status");
    expect(JSON.parse(calls[0].body!).document_ids).toEqual(["id1", "id2"]);
  });

  it("batchGet() calls POST .../documents/batch/get", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    await client.documents.batchGet("docs", ["id1"]);
    expect(calls[0].url).toContain("/documents/batch/get");
  });

  it("batchDelete() calls POST .../documents/batch/delete", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 2, errors: [] });
    await client.documents.batchDelete("docs", ["id1", "id2"]);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/documents/batch/delete");
    expect(JSON.parse(calls[0].body!).document_ids).toEqual(["id1", "id2"]);
  });
});

// ---------------------------------------------------------------------------
// QueryResource
// ---------------------------------------------------------------------------

describe("QueryResource", () => {
  it("query() calls POST /v1/collections/{name}/query", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    await client.queries.query("docs", { query: "hello", top_k: 5 });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/collections/docs/query");
    const body = JSON.parse(calls[0].body!);
    expect(body.query).toBe("hello");
    expect(body.top_k).toBe(5);
  });

  it("multiQuery() calls POST /v1/query", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    await client.queries.multiQuery({ query: "test", collections: ["a", "b"] });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/query");
    expect(JSON.parse(calls[0].body!).collections).toEqual(["a", "b"]);
  });

  it("batchQuery() calls POST /v1/batch/query", async () => {
    const { client, calls } = createMockClient({ results: [] });
    await client.queries.batchQuery({ queries: [{ collection: "docs", query: "test" }] });
    expect(calls[0].url).toContain("/v1/batch/query");
    expect(JSON.parse(calls[0].body!).queries).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// VectorsResource
// ---------------------------------------------------------------------------

describe("VectorsResource", () => {
  it("upsert() calls POST .../vectors/upsert", async () => {
    const { client, calls } = createMockClient({ status: "ok", upserted: 1 });
    await client.vectors.upsert("docs", [{ id: "v1", embedding: [0.1, 0.2], text: "hello" }]);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/vectors/upsert");
    const body = JSON.parse(calls[0].body!);
    expect(body.vectors).toHaveLength(1);
    expect(body.vectors[0].id).toBe("v1");
  });

  it("delete() calls POST .../vectors/delete", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 2 });
    await client.vectors.delete("docs", ["v1", "v2"]);
    expect(calls[0].url).toContain("/vectors/delete");
    expect(JSON.parse(calls[0].body!).ids).toEqual(["v1", "v2"]);
  });
});

// ---------------------------------------------------------------------------
// WebhooksResource
// ---------------------------------------------------------------------------

describe("WebhooksResource", () => {
  it("create() calls POST /v1/admin/webhooks", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.webhooks.create({
      url: "https://example.com/hook",
      events: ["document.ready"],
    });
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/v1/admin/webhooks");
    expect(JSON.parse(calls[0].body!).url).toBe("https://example.com/hook");
  });

  it("list() calls GET /v1/admin/webhooks", async () => {
    const { client, calls } = createMockClient({ webhooks: [] });
    await client.webhooks.list();
    expect(calls[0].url).toContain("/v1/admin/webhooks");
  });

  it("get() calls GET /v1/admin/webhooks/{id}", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.webhooks.get("wh1");
    expect(calls[0].url).toContain("/v1/admin/webhooks/wh1");
  });

  it("update() calls PUT /v1/admin/webhooks/{id}", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.webhooks.update("wh1", { description: "updated" });
    expect(calls[0].method).toBe("PUT");
    expect(JSON.parse(calls[0].body!).description).toBe("updated");
  });

  it("delete() calls DELETE /v1/admin/webhooks/{id}", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.webhooks.delete("wh1");
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toContain("/v1/admin/webhooks/wh1");
  });

  it("listDeliveries() with pagination", async () => {
    const { client, calls } = createMockClient({ deliveries: [], total: 0 });
    await client.webhooks.listDeliveries("wh1", { limit: 10, offset: 20 });
    expect(calls[0].url).toContain("/webhooks/wh1/deliveries");
    expect(calls[0].url).toContain("limit=10");
    expect(calls[0].url).toContain("offset=20");
  });

  it("test() calls POST .../webhooks/{id}/test", async () => {
    const { client, calls } = createMockClient({ status: "delivered" });
    await client.webhooks.test("wh1");
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toContain("/webhooks/wh1/test");
  });
});

// ---------------------------------------------------------------------------
// CollectionClient delegates through resources
// ---------------------------------------------------------------------------

describe("CollectionClient via resources", () => {
  it("query delegates to queries resource", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    const col = client.collection("mydata");
    await col.query({ query: "test" });
    expect(calls[0].url).toContain("/v1/collections/mydata/query");
  });

  it("listDocuments delegates to documents resource", async () => {
    const { client, calls } = createMockClient({ documents: [], total: 0 });
    const col = client.collection("mydata");
    await col.listDocuments({ limit: 5 });
    expect(calls[0].url).toContain("/v1/collections/mydata/documents");
    expect(calls[0].url).toContain("limit=5");
  });

  it("stats delegates to collections resource", async () => {
    const { client, calls } = createMockClient({ collection: "mydata" });
    const col = client.collection("mydata");
    await col.stats();
    expect(calls[0].url).toContain("/v1/collections/mydata/stats");
  });

  it("batchDelete delegates to documents resource", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 1, errors: [] });
    const col = client.collection("mydata");
    await col.batchDelete(["id1"]);
    expect(calls[0].url).toContain("/documents/batch/delete");
  });

  it("reprocessDocument delegates to documents resource", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    const col = client.collection("mydata");
    await col.reprocessDocument("doc1");
    expect(calls[0].url).toContain("/documents/doc1/reprocess");
  });

  it("getDocumentChunks delegates to documents resource", async () => {
    const { client, calls } = createMockClient({ chunks: [], total: 0 });
    const col = client.collection("mydata");
    await col.getDocumentChunks("doc1");
    expect(calls[0].url).toContain("/documents/doc1/chunks");
  });

  it("analytics delegates to client.getAnalytics", async () => {
    const { client, calls } = createMockClient({ collection: "mydata" });
    const col = client.collection("mydata");
    await col.analytics();
    expect(calls[0].url).toContain("/v1/collections/mydata/analytics");
  });
});

// ---------------------------------------------------------------------------
// Backward-compatible flat methods delegate to resources
// ---------------------------------------------------------------------------

describe("backward-compat flat methods", () => {
  it("listCollections delegates to collections.list", async () => {
    const { client, calls } = createMockClient({ collections: [] });
    await client.listCollections();
    expect(calls[0].url).toContain("/v1/collections");
  });

  it("createCollection delegates to collections.create", async () => {
    const { client, calls } = createMockClient({ id: "1" });
    await client.createCollection({ name: "docs" });
    expect(calls[0].method).toBe("POST");
    expect(JSON.parse(calls[0].body!).name).toBe("docs");
  });

  it("getCollection delegates to collections.get", async () => {
    const { client, calls } = createMockClient({ id: "1", name: "docs" });
    await client.getCollection("docs");
    expect(calls[0].url).toContain("/v1/collections/docs");
  });

  it("deleteCollection delegates to collections.delete", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.deleteCollection("docs");
    expect(calls[0].method).toBe("DELETE");
  });

  it("query delegates to queries.query", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    await client.query("docs", { query: "hello" });
    expect(calls[0].url).toContain("/v1/collections/docs/query");
  });

  it("multiQuery delegates to queries.multiQuery", async () => {
    const { client, calls } = createMockClient({ results: [], total: 0 });
    await client.multiQuery({ query: "test", collections: ["a"] });
    expect(calls[0].url).toContain("/v1/query");
  });

  it("batchQuery delegates to queries.batchQuery", async () => {
    const { client, calls } = createMockClient({ results: [] });
    await client.batchQuery({ queries: [{ collection: "docs", query: "test" }] });
    expect(calls[0].url).toContain("/v1/batch/query");
  });

  it("upsertVectors delegates to vectors.upsert", async () => {
    const { client, calls } = createMockClient({ status: "ok", upserted: 1 });
    await client.upsertVectors("docs", [{ id: "v1", embedding: [0.1] }]);
    expect(calls[0].url).toContain("/vectors/upsert");
  });

  it("deleteVectors delegates to vectors.delete", async () => {
    const { client, calls } = createMockClient({ status: "ok", deleted: 1 });
    await client.deleteVectors("docs", ["v1"]);
    expect(calls[0].url).toContain("/vectors/delete");
  });

  it("createWebhook delegates to webhooks.create", async () => {
    const { client, calls } = createMockClient({ id: "wh1" });
    await client.createWebhook({ url: "https://x.com/h", events: ["document.ready"] });
    expect(calls[0].url).toContain("/v1/admin/webhooks");
  });

  it("listWebhooks delegates to webhooks.list", async () => {
    const { client, calls } = createMockClient({ webhooks: [] });
    await client.listWebhooks();
    expect(calls[0].url).toContain("/v1/admin/webhooks");
  });

  it("deleteWebhook delegates to webhooks.delete", async () => {
    const { client, calls } = createMockClient({ status: "ok" });
    await client.deleteWebhook("wh1");
    expect(calls[0].method).toBe("DELETE");
  });

  it("testWebhook delegates to webhooks.test", async () => {
    const { client, calls } = createMockClient({ status: "delivered" });
    await client.testWebhook("wh1");
    expect(calls[0].url).toContain("/webhooks/wh1/test");
  });
});
