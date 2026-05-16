import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { BigRAG } from "@bigrag/client";
import { APIError } from "@bigrag/client";
import {
  API_BASE,
  buildClient,
  cleanupApiKeys,
  cleanupCollections,
  getAdminClient,
  mintApiKey,
  uniqueName,
} from "./helpers.js";

let adminClient: BigRAG;
let adminKeyId: string;

beforeAll(async () => {
  const res = await getAdminClient();
  adminClient = res.client;
  adminKeyId = res.key.id;
});

afterAll(async () => {
  await cleanupCollections();
  await cleanupApiKeys();
});

describe("AuthResource", () => {
  it("setupStatus reports the bootstrap state", async () => {
    const status = await adminClient.auth.setupStatus();
    expect(typeof status.needs_setup).toBe("boolean");
    // The admin has already been provisioned by helpers/Python suite.
    expect(status.needs_setup).toBe(false);
  });

  it("whoami returns api_key auth metadata for a wildcard key", async () => {
    const who = await adminClient.auth.whoami();
    expect(who.authenticated).toBe(true);
    expect(who.auth_method).toBe("api_key");
    expect(typeof who.user_id).toBe("string");
    expect(typeof who.user_email).toBe("string");
    expect(who.api_key_id).toBe(adminKeyId);
    expect(Array.isArray(who.scopes)).toBe(true);
    expect(who.scopes).toEqual(["*:*"]);
    expect(who.collection).toBeNull();
  });

  it("whoami on a scope-limited key reflects the granted scopes", async () => {
    const minted = await mintApiKey({
      name: uniqueName("scope-key"),
      scopes: ["query:read", "document:read"],
    });
    const scoped = buildClient(minted.key);
    const who = await scoped.auth.whoami();
    expect(who.auth_method).toBe("api_key");
    expect(who.api_key_id).toBe(minted.id);
    expect(who.scopes).toEqual(["query:read", "document:read"]);
    expect(who.collection).toBeNull();
  });

  it("whoami on a collection-pinned key surfaces the collection", async () => {
    const collName = uniqueName("authpin");
    const presetId = process.env.BIGRAG_E2E_EMBEDDING_PRESET_ID;
    const body: Parameters<typeof adminClient.collections.create>[0] = {
      name: collName,
      description: "auth pin test",
      vector_store_provider: "qdrant",
      chunk_size: 512,
      chunk_overlap: 50,
      default_top_k: 5,
      default_search_mode: "semantic",
    };
    if (presetId) body.embedding_preset_id = presetId;
    await adminClient.collections.create(body);
    try {
      const minted = await mintApiKey({
        name: uniqueName("pin-key"),
        collection: collName,
      });
      const scoped = buildClient(minted.key);
      const who = await scoped.auth.whoami();
      expect(who.collection).toBe(collName);
    } finally {
      try {
        await adminClient.collections.delete(collName);
      } catch {
        /* ignore */
      }
    }
  });

  it("API-key clients cannot reach admin-only endpoints (admin requires session)", async () => {
    await expect(adminClient.admin.users.list()).rejects.toBeInstanceOf(APIError);
    try {
      await adminClient.admin.users.list();
    } catch (err) {
      const e = err as APIError;
      expect(e.status).toBe(403);
    }
  });

  it("login over the SDK with bogus credentials raises APIError(401)", async () => {
    const unauth = buildClient("", { baseUrl: API_BASE });
    await expect(
      unauth.auth.login({ email: "nobody@example.com", password: "wrong-pw" }),
    ).rejects.toMatchObject({ status: 401 });
  });

  it("logout returns ok even on an api-key client (no session cookie present)", async () => {
    const resp = await adminClient.auth.logout();
    expect(resp.status).toBe("ok");
  });

  it("logoutAll requires session auth and rejects api-key clients", async () => {
    await expect(adminClient.auth.logoutAll()).rejects.toBeInstanceOf(APIError);
    try {
      await adminClient.auth.logoutAll();
    } catch (err) {
      expect((err as APIError).status).toBe(403);
    }
  });
});
