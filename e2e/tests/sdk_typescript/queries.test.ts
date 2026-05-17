import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { BigRAG, Collection } from "@bigrag/client";
import {
  cleanupApiKeys,
  cleanupCollections,
  createCollection,
  getAdminClient,
  uploadFixture,
} from "./helpers.js";

let client: BigRAG;
let collA: Collection;
let collB: Collection;

beforeAll(async () => {
  ({ client } = await getAdminClient());
  collA = await createCollection(client);
  collB = await createCollection(client);
  // Seed each collection with a document so queries return real results.
  await uploadFixture(client, collA.name, "sample.txt");
  await uploadFixture(client, collA.name, "sample.md");
  await uploadFixture(client, collB.name, "sample.html");
});

afterAll(async () => {
  await cleanupCollections();
  await cleanupApiKeys();
});

describe("QueryResource", () => {
  it("query returns results with the expected envelope and top_k respected", async () => {
    const resp = await client.queries.query(collA.name, {
      query: "what is bigrag",
      top_k: 3,
    });
    expect(resp.query).toBe("what is bigrag");
    expect(resp.collection).toBe(collA.name);
    expect(Array.isArray(resp.results)).toBe(true);
    expect(resp.results.length).toBeLessThanOrEqual(3);
    expect(typeof resp.total).toBe("number");
    for (const r of resp.results) {
      expect(typeof r.id).toBe("string");
      expect(typeof r.text).toBe("string");
      expect(typeof r.score).toBe("number");
    }
  });

  it("query supports search_mode = keyword (alternative path)", async () => {
    const resp = await client.queries.query(collA.name, {
      query: "sample",
      top_k: 5,
      search_mode: "keyword",
    });
    expect(resp.query).toBe("sample");
    expect(Array.isArray(resp.results)).toBe(true);
  });

  it("query supports filters payload without erroring", async () => {
    const resp = await client.queries.query(collA.name, {
      query: "anything",
      top_k: 5,
      filters: { does_not_exist: "x" },
    });
    expect(Array.isArray(resp.results)).toBe(true);
  });

  it("multiQuery searches across multiple collections", async () => {
    const resp = await client.queries.multiQuery({
      query: "sample",
      collections: [collA.name, collB.name],
      top_k: 5,
    });
    expect(resp.query).toBe("sample");
    expect(resp.collections).toEqual(expect.arrayContaining([collA.name, collB.name]));
    expect(Array.isArray(resp.results)).toBe(true);
    expect(typeof resp.total).toBe("number");
    for (const r of resp.results) {
      expect([collA.name, collB.name]).toContain(r.collection);
    }
  });

  it("batchQuery executes a list of queries and returns per-item results", async () => {
    const resp = await client.queries.batchQuery({
      queries: [
        { collection: collA.name, query: "sample", top_k: 2 },
        { collection: collB.name, query: "sample", top_k: 2 },
      ],
    });
    expect(Array.isArray(resp.results)).toBe(true);
    expect(resp.results.length).toBe(2);
    expect(resp.results[0].collection).toBe(collA.name);
    expect(resp.results[1].collection).toBe(collB.name);
    for (const item of resp.results) {
      expect(typeof item.query).toBe("string");
      expect(Array.isArray(item.results)).toBe(true);
      expect(item.results.length).toBeLessThanOrEqual(2);
    }
  });

  it("query top_k caps the number of hits", async () => {
    const big = await client.queries.query(collA.name, { query: "sample", top_k: 1 });
    expect(big.results.length).toBeLessThanOrEqual(1);
  });
});
