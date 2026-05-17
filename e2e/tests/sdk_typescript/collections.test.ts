import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { BigRAG, Collection } from "@bigrag/client";
import { APIError } from "@bigrag/client";
import { cleanupApiKeys, cleanupCollections, getAdminClient, uniqueName } from "./helpers.js";

let client: BigRAG;

beforeAll(async () => {
  ({ client } = await getAdminClient());
});

afterAll(async () => {
  await cleanupCollections();
  await cleanupApiKeys();
});

async function createTempCollection(): Promise<Collection> {
  const presetId = process.env.BIGRAG_E2E_EMBEDDING_PRESET_ID;
  const body: Parameters<typeof client.collections.create>[0] = {
    name: uniqueName("sdkcoll"),
    description: "sdk collections.test",
    vector_store_provider: "qdrant",
    dimension: 1536,
    chunk_size: 512,
    chunk_overlap: 50,
    chunk_strategy: "paragraph",
    default_top_k: 5,
    default_search_mode: "semantic",
    reranking_enabled: false,
  };
  if (presetId) body.embedding_preset_id = presetId;
  return client.collections.create(body);
}

describe("CollectionsResource", () => {
  it("create returns a Collection with expected fields", async () => {
    const created = await createTempCollection();
    expect(typeof created.id).toBe("string");
    expect(created.id.length).toBeGreaterThan(0);
    expect(typeof created.name).toBe("string");
    expect(created.vector_store_provider).toBe("qdrant");
    expect(typeof created.dimension).toBe("number");
    expect(created.dimension).toBeGreaterThan(0);
    expect(created.document_count).toBe(0);
    expect(typeof created.created_at).toBe("string");
    expect(typeof created.updated_at).toBe("string");
  });

  it("get returns the previously created collection", async () => {
    const created = await createTempCollection();
    const fetched = await client.collections.get(created.name);
    expect(fetched.id).toBe(created.id);
    expect(fetched.name).toBe(created.name);
  });

  it("list returns paged response and includes our collection", async () => {
    const created = await createTempCollection();
    const page = await client.collections.list({ limit: 100 });
    expect(typeof page.total).toBe("number");
    expect(Array.isArray(page.collections)).toBe(true);
    expect(page.collections.some((c) => c.name === created.name)).toBe(true);
  });

  it("list supports name filter", async () => {
    const created = await createTempCollection();
    const page = await client.collections.list({ name: created.name });
    expect(page.collections.length).toBeGreaterThanOrEqual(1);
    for (const c of page.collections) {
      expect(c.name.includes(created.name) || c.name === created.name).toBe(true);
    }
  });

  it("update mutates description and returns updated collection", async () => {
    const created = await createTempCollection();
    const updated = await client.collections.update(created.name, {
      description: "updated by sdk test",
      default_top_k: 7,
    });
    expect(updated.description).toBe("updated by sdk test");
    expect(updated.default_top_k).toBe(7);
  });

  it("stats returns counts for an empty collection", async () => {
    const created = await createTempCollection();
    const stats = await client.collections.stats(created.name);
    expect(stats.collection).toBe(created.name);
    expect(stats.document_count).toBe(0);
    expect(stats.total_chunks).toBe(0);
    expect(typeof stats.total_tokens).toBe("number");
    expect(typeof stats.total_size_bytes).toBe("number");
    expect(typeof stats.status_counts).toBe("object");
  });

  it("truncate returns ok status", async () => {
    const created = await createTempCollection();
    const resp = await client.collections.truncate(created.name);
    expect(resp.status).toBe("ok");
  });

  it("reembed returns ok status for an empty collection", async () => {
    const created = await createTempCollection();
    const resp = await client.collections.reembed(created.name);
    expect(resp.status).toBe("ok");
  });

  it("delete returns ok and subsequent get raises APIError(404)", async () => {
    const created = await createTempCollection();
    const del = await client.collections.delete(created.name);
    expect(del.status).toBe("ok");
    await expect(client.collections.get(created.name)).rejects.toBeInstanceOf(APIError);
    try {
      await client.collections.get(created.name);
    } catch (err) {
      const e = err as APIError;
      expect(e.status).toBe(404);
      expect(typeof e.message).toBe("string");
    }
  });

  it("get on unknown name raises APIError(404)", async () => {
    await expect(client.collections.get(uniqueName("nope"))).rejects.toMatchObject({
      name: "APIError",
      status: 404,
    });
  });
});
