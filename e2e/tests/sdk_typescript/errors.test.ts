import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { BigRAG } from "@bigrag/client";
import { APIConnectionError, APIError, APITimeoutError, BigRAGError } from "@bigrag/client";
import {
  API_BASE,
  buildClient,
  cleanupApiKeys,
  cleanupCollections,
  createCollection,
  getAdminClient,
  uniqueName,
} from "./helpers.js";

let admin: BigRAG;

beforeAll(async () => {
  ({ client: admin } = await getAdminClient());
});

afterAll(async () => {
  await cleanupCollections();
  await cleanupApiKeys();
});

describe("SDK error classes", () => {
  it("APIError is exported and inherits from BigRAGError", () => {
    const e = new APIError(404, "x", "not_found");
    expect(e).toBeInstanceOf(APIError);
    expect(e).toBeInstanceOf(BigRAGError);
    expect(e.status).toBe(404);
    expect(e.code).toBe("not_found");
    expect(e.message).toBe("x");
    expect(e.name).toBe("APIError");
  });

  it("APIConnectionError and APITimeoutError are exported and inherit from BigRAGError", () => {
    expect(new APIConnectionError()).toBeInstanceOf(BigRAGError);
    expect(new APITimeoutError()).toBeInstanceOf(BigRAGError);
  });

  it("APIError(401) on an invalid bearer token", async () => {
    const bad = buildClient("bigrag_sk_obviously_invalid_xxxxxxxxxxxxxxxx");
    try {
      await bad.auth.whoami();
      throw new Error("expected APIError");
    } catch (err) {
      expect(err).toBeInstanceOf(APIError);
      const e = err as APIError;
      expect(e.status).toBe(401);
      expect(typeof e.message).toBe("string");
      expect(e.message.length).toBeGreaterThan(0);
    }
  });

  it("APIError(401) on a missing bearer token", async () => {
    const unauth = buildClient("");
    try {
      await unauth.auth.whoami();
      throw new Error("expected APIError");
    } catch (err) {
      expect(err).toBeInstanceOf(APIError);
      expect((err as APIError).status).toBe(401);
    }
  });

  it("APIError(404) on an unknown collection", async () => {
    try {
      await admin.collections.get(uniqueName("nope"));
      throw new Error("expected APIError");
    } catch (err) {
      expect(err).toBeInstanceOf(APIError);
      expect((err as APIError).status).toBe(404);
    }
  });

  it("APIError with a 4xx (validation) on a malformed create body", async () => {
    try {
      await admin.collections.create({
        name: "", // server-side validation: name must be non-empty
        description: "bad",
      });
      throw new Error("expected APIError");
    } catch (err) {
      expect(err).toBeInstanceOf(APIError);
      const e = err as APIError;
      expect(e.status).toBeGreaterThanOrEqual(400);
      expect(e.status).toBeLessThan(500);
    }
  });

  it("APIError(403) when a scope-limited key calls an unauthorized endpoint", async () => {
    const target = await createCollection(admin);
    const restricted = await createCollection(admin, {
      name: uniqueName("ro"),
      description: "scope test",
    });
    // mintApiKey via session — read-only scope.
    const { mintApiKey } = await import("./helpers.js");
    const minted = await mintApiKey({
      name: uniqueName("read-only"),
      scopes: ["query:read"],
    });
    const scoped = buildClient(minted.key);
    try {
      // trying to upload a document requires document:upload scope.
      await scoped.documents.upload(
        target.name,
        new File([new Blob([new Uint8Array(Buffer.from("hi"))])], "x.txt"),
      );
      throw new Error("expected APIError");
    } catch (err) {
      expect(err).toBeInstanceOf(APIError);
      expect((err as APIError).status).toBe(403);
    } finally {
      try {
        await admin.collections.delete(restricted.name);
      } catch {
        /* ignore */
      }
    }
  });

  it("APIConnectionError when baseUrl is unreachable", async () => {
    const unreachable = buildClient("anything", {
      baseUrl: "http://127.0.0.1:1",
    });
    try {
      await unreachable.health();
      throw new Error("expected APIConnectionError");
    } catch (err) {
      expect(err).toBeInstanceOf(BigRAGError);
      expect(err).toBeInstanceOf(APIConnectionError);
    }
  }, 15_000);

  it("error objects expose .status, .code, and .message", async () => {
    try {
      await admin.collections.get(uniqueName("missing"));
      throw new Error("expected APIError");
    } catch (err) {
      const e = err as APIError;
      expect(e).toBeInstanceOf(APIError);
      expect(typeof e.status).toBe("number");
      expect(typeof e.message).toBe("string");
      // .code may be undefined if the server didn't include an error.code field.
      expect(["string", "undefined"]).toContain(typeof e.code);
    }
  });

  it("base URL trailing slash is normalized so requests still succeed", async () => {
    const normalized = buildClient("", { baseUrl: `${API_BASE}/` });
    const h = await normalized.health();
    expect(h.status).toBe("ok");
  });
});
