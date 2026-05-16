import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { BigRAG, Collection } from "@bigrag/client";
import { APIError } from "@bigrag/client";
import {
  cleanupApiKeys,
  cleanupCollections,
  createCollection,
  fixturePath,
  getAdminClient,
  readFixture,
  uniqueName,
  uploadFixture,
  waitForDocument,
} from "./helpers.js";

let client: BigRAG;
let coll: Collection;

beforeAll(async () => {
  ({ client } = await getAdminClient());
  coll = await createCollection(client);
});

afterAll(async () => {
  await cleanupCollections();
  await cleanupApiKeys();
});

describe("DocumentsResource", () => {
  it("upload from a buffer reaches ready status and is listable/gettable", async () => {
    const buf = await readFixture("sample.txt");
    const blob = new Blob([new Uint8Array(buf)]);
    const file = new File([blob], "uploaded.txt", { type: "text/plain" });
    const uploaded = await client.documents.upload(coll.name, file);
    expect(typeof uploaded.id).toBe("string");
    expect(uploaded.collection_id).toBe(coll.id);
    expect(uploaded.filename).toBe("uploaded.txt");
    expect(typeof uploaded.file_size).toBe("number");

    const ready = await waitForDocument(client, coll.name, uploaded.id);
    expect(ready.status).toBe("ready");
    expect(ready.chunk_count).toBeGreaterThan(0);

    const got = await client.documents.get(coll.name, uploaded.id);
    expect(got.id).toBe(uploaded.id);

    const page = await client.documents.list(coll.name, { limit: 100 });
    expect(Array.isArray(page.documents)).toBe(true);
    expect(page.documents.some((d) => d.id === uploaded.id)).toBe(true);
  });

  it("upload via {path} option reads file from disk", async () => {
    const doc = await client.documents.upload(coll.name, {
      path: fixturePath("sample.md"),
      name: uniqueName("md") + ".md",
    });
    expect(doc.filename.endsWith(".md")).toBe(true);
    const ready = await waitForDocument(client, coll.name, doc.id);
    expect(ready.status).toBe("ready");
  });

  it("dedup: re-uploading the same content returns deduped=true", async () => {
    const local = await createCollection(client);
    const buf = await readFixture("sample.txt");
    const blob1 = new Blob([new Uint8Array(buf)]);
    const blob2 = new Blob([new Uint8Array(buf)]);
    const first = await client.documents.upload(
      local.name,
      new File([blob1], "dedup.txt", { type: "text/plain" }),
    );
    const firstReady = await waitForDocument(client, local.name, first.id);
    expect(firstReady.status).toBe("ready");

    const second = await client.documents.upload(
      local.name,
      new File([blob2], "dedup.txt", { type: "text/plain" }),
    );
    expect(second.deduped).toBe(true);
    expect(second.id).toBe(first.id);
  });

  it("getChunks returns the chunks of a ready document", async () => {
    const doc = await uploadFixture(client, coll.name, "sample.md");
    const chunks = await client.documents.getChunks(coll.name, doc.id, { limit: 100 });
    expect(Array.isArray(chunks.chunks)).toBe(true);
    expect(chunks.chunks.length).toBeGreaterThan(0);
    expect(typeof chunks.total).toBe("number");
    const first = chunks.chunks[0];
    expect(first.document_id).toBe(doc.id);
    expect(typeof first.chunk_index).toBe("number");
    expect(typeof first.text).toBe("string");
  });

  it("batchUpload uploads multiple files and returns a list response", async () => {
    const local = await createCollection(client);
    const b1 = await readFixture("sample.txt");
    const b2 = await readFixture("sample.md");
    const f1 = new File([new Blob([new Uint8Array(b1)])], uniqueName("a") + ".txt");
    const f2 = new File([new Blob([new Uint8Array(b2)])], uniqueName("b") + ".md");
    const resp = await client.documents.batchUpload(local.name, [f1, f2]);
    expect(typeof resp.total).toBe("number");
    expect(resp.documents.length).toBe(2);
    for (const d of resp.documents) {
      await waitForDocument(client, local.name, d.id);
    }
  });

  it("batchGetStatus + batchGet + batchDelete operate on a set of ids", async () => {
    const local = await createCollection(client);
    const docs = await Promise.all(
      [0, 1, 2].map(async (i) => {
        const buf = await readFixture("sample.txt");
        const f = new File(
          [new Blob([new Uint8Array(buf)])],
          uniqueName(`b${i}`) + ".txt",
        );
        return client.documents.upload(local.name, f);
      }),
    );
    for (const d of docs) await waitForDocument(client, local.name, d.id);
    const ids = docs.map((d) => d.id);

    const status = await client.documents.batchGetStatus(local.name, ids);
    expect(status.total).toBeGreaterThanOrEqual(ids.length);
    const knownIds = new Set(status.documents.map((s) => s.id));
    for (const id of ids) expect(knownIds.has(id)).toBe(true);

    const got = await client.documents.batchGet(local.name, ids);
    expect(got.documents.length).toBe(ids.length);

    const del = await client.documents.batchDelete(local.name, ids);
    expect(del.status).toBe("ok");
    expect(del.deleted).toBe(ids.length);
    expect(Array.isArray(del.errors)).toBe(true);
  });

  it("delete removes a document and subsequent get raises APIError(404)", async () => {
    const doc = await uploadFixture(client, coll.name, "sample.txt", {
      filename: uniqueName("del") + ".txt",
    });
    const del = await client.documents.delete(coll.name, doc.id);
    expect(del.status).toBe("ok");
    await expect(client.documents.get(coll.name, doc.id)).rejects.toBeInstanceOf(APIError);
  });

  it("get on unknown document id raises APIError(404)", async () => {
    await expect(
      client.documents.get(coll.name, "00000000-0000-0000-0000-000000000000"),
    ).rejects.toMatchObject({ status: 404 });
  });
});
