import { describe, expect, it, vi } from "vitest";
import type { RequestClient } from "./core.js";
import { NotFoundError } from "./errors.js";
import {
  AdminResource,
  AuthResource,
  ChatResource,
  CollectionsResource,
  ConnectorsResource,
  DocumentsResource,
  EvaluationsResource,
  QueryResource,
  VectorsResource,
  WebhooksResource,
} from "./resources/index.js";

type RequestCall = [string, string, { json?: unknown; params?: Record<string, string> }?];
type FormCall = [string, FormData];

function createClient() {
  const requestCalls: RequestCall[] = [];
  const formCalls: FormCall[] = [];
  const client = {
    apiKey: "bigrag_sk_test",
    baseUrl: "http://api.local",
    _fetch: vi.fn(),
    _request: vi.fn(async (...args: RequestCall) => {
      requestCalls.push(args);
      return { status: "ok" };
    }),
    _requestFormData: vi.fn(async (...args: FormCall) => {
      formCalls.push(args);
      return { status: "ok" };
    }),
  };
  return { client: client as unknown as RequestClient, requestCalls, formCalls };
}

const streamResponse = (chunks: string[]) =>
  new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
        controller.close();
      },
    }),
  );

describe("resource wrappers", () => {
  it("builds admin resource requests", async () => {
    const { client, requestCalls } = createClient();
    const admin = new AdminResource(client);

    await admin.users.list({ limit: 2, offset: 4 });
    await admin.users.create({ email: "a@example.com", password: "secret123", role: "admin" });
    await admin.users.update("user/1", { role: "member" });
    await admin.users.delete("user/1");
    await admin.apiKeys.list({ limit: 3 });
    await admin.apiKeys.create({ name: "ci", scopes: ["collections:read"] });
    await admin.apiKeys.update("key/1", { name: "prod" });
    await admin.apiKeys.delete("key/1");
    await admin.access.logs({
      action: "query",
      actorId: "actor",
      collection: "docs",
      method: "POST",
      path: "/v1/query",
      statusFamily: "2xx",
      success: false,
      limit: 10,
      offset: 20,
    });
    await admin.access.overview({ windowDays: 14 });
    await admin.audit.list({ action: "create", actorId: "actor", resourceType: "collection" });
    await admin.connectors.google.get();
    await admin.connectors.google.update({ enabled: true });
    await admin.embeddingPresets.list({ offset: 1 });
    await admin.embeddingPresets.create({
      name: "preset",
      provider: "openai",
      model: "text-embedding-3-small",
      dimensions: 1536,
    });
    await admin.embeddingPresets.update("preset/1", { name: "renamed" });
    await admin.embeddingPresets.delete("preset/1");
    await admin.mcpServers.list();
    await admin.mcpServers.create({ name: "local", base_url: "http://localhost:4001" });
    await admin.mcpServers.update("srv/1", { name: "renamed" });
    await admin.mcpServers.rotate("srv/1");
    await admin.mcpServers.delete("srv/1");

    expect(requestCalls).toEqual([
      ["GET", "/v1/admin/users", { params: { limit: "2", offset: "4" } }],
      [
        "POST",
        "/v1/admin/users",
        { json: { email: "a@example.com", password: "secret123", role: "admin" } },
      ],
      ["PATCH", "/v1/admin/users/user%2F1", { json: { role: "member" } }],
      ["DELETE", "/v1/admin/users/user%2F1"],
      ["GET", "/v1/admin/api-keys", { params: { limit: "3" } }],
      ["POST", "/v1/admin/api-keys", { json: { name: "ci", scopes: ["collections:read"] } }],
      ["PATCH", "/v1/admin/api-keys/key%2F1", { json: { name: "prod" } }],
      ["DELETE", "/v1/admin/api-keys/key%2F1"],
      [
        "GET",
        "/v1/admin/access/logs",
        {
          params: {
            limit: "10",
            offset: "20",
            action: "query",
            actor_id: "actor",
            collection: "docs",
            method: "POST",
            path: "/v1/query",
            status_family: "2xx",
            success: "false",
          },
        },
      ],
      ["GET", "/v1/admin/access/overview", { params: { window_days: "14" } }],
      [
        "GET",
        "/v1/admin/audit",
        { params: { action: "create", actor_id: "actor", resource_type: "collection" } },
      ],
      ["GET", "/v1/admin/connectors/google"],
      ["PUT", "/v1/admin/connectors/google", { json: { enabled: true } }],
      ["GET", "/v1/admin/embedding-presets", { params: { offset: "1" } }],
      [
        "POST",
        "/v1/admin/embedding-presets",
        {
          json: {
            name: "preset",
            provider: "openai",
            model: "text-embedding-3-small",
            dimensions: 1536,
          },
        },
      ],
      ["PATCH", "/v1/admin/embedding-presets/preset%2F1", { json: { name: "renamed" } }],
      ["DELETE", "/v1/admin/embedding-presets/preset%2F1"],
      ["GET", "/v1/admin/mcp-servers"],
      [
        "POST",
        "/v1/admin/mcp-servers",
        { json: { name: "local", base_url: "http://localhost:4001" } },
      ],
      ["PATCH", "/v1/admin/mcp-servers/srv%2F1", { json: { name: "renamed" } }],
      ["POST", "/v1/admin/mcp-servers/srv%2F1/rotate"],
      ["DELETE", "/v1/admin/mcp-servers/srv%2F1"],
    ]);
  });

  it("builds auth and platform-adjacent resource requests", async () => {
    const { client, requestCalls } = createClient();
    const auth = new AuthResource(client);
    const evaluations = new EvaluationsResource(client);

    await auth.setupStatus();
    await auth.setup({ email: "a@example.com", password: "secret123", name: "Admin" });
    await auth.login({ email: "a@example.com", password: "secret123" });
    await auth.logout();
    await auth.logoutAll();
    await auth.me();
    await auth.whoami();
    await auth.changePassword({ current_password: "old", new_password: "new-secret" });
    await auth.preferences();
    await auth.updatePreferences({ theme: "dark" });
    await evaluations.run({ collection: "docs", questions: [] });

    expect(requestCalls).toEqual([
      ["GET", "/v1/auth/setup-status"],
      [
        "POST",
        "/v1/auth/setup",
        { json: { email: "a@example.com", password: "secret123", name: "Admin" } },
      ],
      ["POST", "/v1/auth/login", { json: { email: "a@example.com", password: "secret123" } }],
      ["POST", "/v1/auth/logout"],
      ["POST", "/v1/auth/logout-all"],
      ["GET", "/v1/auth/me"],
      ["GET", "/v1/auth/whoami"],
      [
        "POST",
        "/v1/auth/password",
        { json: { current_password: "old", new_password: "new-secret" } },
      ],
      ["GET", "/v1/auth/preferences"],
      ["PUT", "/v1/auth/preferences", { json: { theme: "dark" } }],
      ["POST", "/v1/evaluation", { json: { collection: "docs", questions: [] } }],
    ]);
  });

  it("builds chat resource requests", async () => {
    const { client, requestCalls } = createClient();
    const chat = new ChatResource(client);

    await chat.create({ message: "hello", collection: "docs" });
    await chat.list({ limit: 10, offset: 20 });
    await chat.get("conversation/1");
    await chat.update("conversation/1", { title: "Renamed" });
    await chat.delete("conversation/1");

    expect(requestCalls).toEqual([
      ["POST", "/v1/chat", { json: { message: "hello", collection: "docs", stream: false } }],
      ["GET", "/v1/chat", { params: { limit: "10", offset: "20" } }],
      ["GET", "/v1/chat/conversation/1"],
      ["PATCH", "/v1/chat/conversation/1", { json: { title: "Renamed" } }],
      ["DELETE", "/v1/chat/conversation/1"],
    ]);
  });

  it("streams chat events with auth and split frames", async () => {
    const fetch = vi.fn(async () =>
      streamResponse([
        'event: delta\ndata: {"delta":"hel',
        'lo"}\n\ndata: [DONE]\n\n',
        'event: done\ndata: {"ok":true}\n\n',
      ]),
    );
    const client = {
      apiKey: "bigrag_sk_test",
      baseUrl: "http://api.local",
      _fetch: fetch,
      _request: vi.fn(),
      _requestFormData: vi.fn(),
    } as unknown as RequestClient;
    const chat = new ChatResource(client);

    const events = [];
    for await (const event of chat.stream({ message: "hello", collection: "docs" })) {
      events.push(event);
    }

    expect(events).toEqual([
      { event: "delta", data: { delta: "hello" } },
      { event: "done", data: { ok: true } },
    ]);
    expect(fetch).toHaveBeenCalledWith(
      "http://api.local/v1/chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer bigrag_sk_test",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({ message: "hello", collection: "docs", stream: true }),
      }),
    );
  });

  it("surfaces chat stream response and parse errors", async () => {
    const errorClient = {
      apiKey: "",
      baseUrl: "http://api.local",
      _fetch: vi.fn(async () => new Response("bad key", { status: 401, statusText: "Nope" })),
      _request: vi.fn(),
      _requestFormData: vi.fn(),
    } as unknown as RequestClient;

    await expect(
      new ChatResource(errorClient).stream({ message: "hello", collection: "docs" }).next(),
    ).rejects.toThrow("bad key");

    const malformedClient = {
      apiKey: "",
      baseUrl: "http://api.local",
      _fetch: vi.fn(async () => streamResponse(["event: delta\ndata: nope\n\n"])),
      _request: vi.fn(),
      _requestFormData: vi.fn(),
    } as unknown as RequestClient;

    await expect(
      new ChatResource(malformedClient).stream({ message: "hello", collection: "docs" }).next(),
    ).rejects.toThrow();
  });

  it("builds collection and connector resource requests", async () => {
    const { client, requestCalls } = createClient();
    const collections = new CollectionsResource(client);
    const connectors = new ConnectorsResource(client);

    await collections.list({ name: "docs", limit: 2, offset: 4 });
    await collections.get("team docs");
    await collections.create({ name: "docs" });
    await collections.update("team docs", { metadata: { owner: "search" } });
    await collections.delete("team docs");
    await collections.stats("team docs");
    await collections.truncate("team docs");
    await collections.reembed("team docs");
    await collections.analytics("team docs");
    await connectors.google.account();
    await connectors.google.files({
      parentId: "folder",
      query: "pdf",
      pageToken: "next",
      pageSize: 50,
    });
    await connectors.google.oauthStartUrl({ redirectPath: "/settings" });
    await connectors.google.disconnect();
    await connectors.google.sources({ collection: "docs" });
    await connectors.google.createSource({ collection: "docs", folder_id: "folder" });
    await connectors.google.updateSource("source/1", { enabled: false });
    await connectors.google.deleteSource("source/1");
    await connectors.google.syncSource("source/1");
    await connectors.google.syncJobs({ collection: "docs", sourceId: "source/1", limit: 5 });

    expect(requestCalls).toEqual([
      ["GET", "/v1/collections", { params: { name: "docs", limit: "2", offset: "4" } }],
      ["GET", "/v1/collections/team%20docs"],
      ["POST", "/v1/collections", { json: { name: "docs" } }],
      ["PUT", "/v1/collections/team%20docs", { json: { metadata: { owner: "search" } } }],
      ["DELETE", "/v1/collections/team%20docs"],
      ["GET", "/v1/collections/team%20docs/stats"],
      ["POST", "/v1/collections/team%20docs/truncate"],
      ["POST", "/v1/collections/team%20docs/reembed"],
      ["GET", "/v1/collections/team%20docs/analytics"],
      ["GET", "/v1/connectors/google/account"],
      [
        "GET",
        "/v1/connectors/google/files",
        { params: { parent_id: "folder", query: "pdf", page_token: "next", page_size: "50" } },
      ],
      ["GET", "/v1/connectors/google/oauth/start-url", { params: { redirect_path: "/settings" } }],
      ["POST", "/v1/connectors/google/disconnect"],
      ["GET", "/v1/connectors/google/sources", { params: { collection: "docs" } }],
      [
        "POST",
        "/v1/connectors/google/sources",
        { json: { collection: "docs", folder_id: "folder" } },
      ],
      ["PATCH", "/v1/connectors/google/sources/source%2F1", { json: { enabled: false } }],
      ["DELETE", "/v1/connectors/google/sources/source%2F1"],
      ["POST", "/v1/connectors/google/sources/source%2F1/sync"],
      [
        "GET",
        "/v1/connectors/google/sync-jobs",
        { params: { collection: "docs", source_id: "source/1", limit: "5" } },
      ],
    ]);
  });

  it("streams collection events with auth and maps errors", async () => {
    const { client } = createClient();
    client._fetch = vi.fn(async () =>
      streamResponse([
        'data: {"step":"chunking","message":"working","progress":50}\n\n',
        'data: {"step":"done","message":"ok","progress":100,"status":"complete"}\n\n',
      ]),
    );
    const collections = new CollectionsResource(client);

    const events = [];
    for await (const event of collections.streamEvents("team docs")) {
      events.push(event);
    }

    expect(events).toEqual([
      { step: "chunking", message: "working", progress: 50 },
      { step: "done", message: "ok", progress: 100, status: "complete" },
    ]);
    expect(client._fetch).toHaveBeenCalledWith(
      "http://api.local/v1/collections/team%20docs/events",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer bigrag_sk_test" }),
      }),
    );

    client._fetch = vi.fn(async () => new Response("missing", { status: 404, statusText: "Gone" }));

    await expect(collections.streamEvents("missing").next()).rejects.toBeInstanceOf(NotFoundError);
  });

  it("builds document resource requests", async () => {
    const { client, requestCalls, formCalls } = createClient();
    const documents = new DocumentsResource(client);

    await documents.upload("team docs", new Uint8Array([1, 2, 3]), { tenant: "acme" });
    await documents.batchUpload("team docs", [new Uint8Array([1]), new Uint8Array([2])]);
    await documents.createUploadSession("team docs", { total_files: 2, total_bytes: 10 });
    await documents.getUploadSession("team docs", "session/1");
    await documents.uploadSessionFile("team docs", "session/1", new Uint8Array([1]), {
      clientItemId: "item-1",
      filename: "note.txt",
    });
    await documents.completeUploadSession("team docs", "session/1");
    await documents.cancelUploadSession("team docs", "session/1");
    await documents.list("team docs", { status: "ready", limit: 5, offset: 10 });
    await documents.get("team docs", "doc/1");
    await documents.delete("team docs", "doc/1");
    await documents.reprocess("team docs", "doc/1");
    await documents.getChunks("team docs", "doc/1", { limit: 3, offset: 6 });
    await documents.batchGetStatus("team docs", ["doc/1"]);
    await documents.batchGet("team docs", ["doc/1"]);
    await documents.batchDelete("team docs", ["doc/1"]);
    await documents.getById("doc/1");
    await documents.getChunksById("doc/1", { limit: 1 });

    expect(documents.getFileUrl("team docs", "doc/1")).toBe(
      "http://api.local/v1/collections/team%20docs/documents/doc%2F1/file",
    );
    expect(formCalls.map(([path]) => path)).toEqual([
      "/v1/collections/team%20docs/documents",
      "/v1/collections/team%20docs/documents/batch/upload",
      "/v1/collections/team%20docs/upload-sessions/session%2F1/files",
    ]);
    expect(requestCalls).toEqual([
      [
        "POST",
        "/v1/collections/team%20docs/upload-sessions",
        { json: { total_files: 2, total_bytes: 10, metadata: {} } },
      ],
      ["GET", "/v1/collections/team%20docs/upload-sessions/session%2F1"],
      ["POST", "/v1/collections/team%20docs/upload-sessions/session%2F1/complete"],
      ["POST", "/v1/collections/team%20docs/upload-sessions/session%2F1/cancel"],
      [
        "GET",
        "/v1/collections/team%20docs/documents",
        { params: { status: "ready", limit: "5", offset: "10" } },
      ],
      ["GET", "/v1/collections/team%20docs/documents/doc%2F1"],
      ["DELETE", "/v1/collections/team%20docs/documents/doc%2F1"],
      ["POST", "/v1/collections/team%20docs/documents/doc%2F1/reprocess"],
      [
        "GET",
        "/v1/collections/team%20docs/documents/doc%2F1/chunks",
        { params: { limit: "3", offset: "6" } },
      ],
      [
        "POST",
        "/v1/collections/team%20docs/documents/batch/status",
        { json: { document_ids: ["doc/1"] } },
      ],
      [
        "POST",
        "/v1/collections/team%20docs/documents/batch/get",
        { json: { document_ids: ["doc/1"] } },
      ],
      [
        "POST",
        "/v1/collections/team%20docs/documents/batch/delete",
        { json: { document_ids: ["doc/1"] } },
      ],
      ["GET", "/v1/documents/doc%2F1"],
      ["GET", "/v1/documents/doc%2F1/chunks", { params: { limit: "1" } }],
    ]);
  });

  it("builds query, vector, webhook, and pagination requests", async () => {
    const { client, requestCalls } = createClient();
    const queries = new QueryResource(client);
    const vectors = new VectorsResource(client);
    const webhooks = new WebhooksResource(client);
    const collections = new CollectionsResource(client);
    const documents = new DocumentsResource(client);

    await queries.query("team docs", { query: "hello" });
    await queries.multiQuery({ collections: ["docs"], query: "hello" });
    await queries.batchQuery({ queries: [{ collection: "docs", query: "hello" }] });
    await vectors.upsert("team docs", [{ id: "vec/1", vector: [0.1], metadata: { a: 1 } }]);
    await vectors.delete("team docs", ["vec/1"]);
    await webhooks.create({ url: "https://example.com/hook", events: ["document.created"] });
    await webhooks.list();
    await webhooks.get("hook/1");
    await webhooks.update("hook/1", { enabled: false });
    await webhooks.delete("hook/1");
    await webhooks.listDeliveries("hook/1", { limit: 2, offset: 4 });
    await webhooks.test("hook/1");
    await webhooks.replayDelivery("hook/1", "delivery/1");

    requestCalls.length = 0;
    client._request = vi.fn(
      async (_method: string, _path: string, opts?: { params?: Record<string, string> }) => {
        const offset = Number(opts?.params?.offset ?? "0");
        if (_path.endsWith("/documents")) {
          return {
            documents: offset === 0 ? [{ id: "doc-1" }, { id: "doc-2" }] : [{ id: "doc-3" }],
            total: 3,
          };
        }
        return {
          collections: offset === 0 ? [{ name: "a" }, { name: "b" }] : [{ name: "c" }],
          total: 3,
        };
      },
    ) as RequestClient["_request"];

    const allCollections = [];
    for await (const collection of collections.listAll({ limit: 2 }))
      allCollections.push(collection);
    const allDocuments = [];
    for await (const document of documents.listAll("docs", { limit: 2 }))
      allDocuments.push(document);

    expect(allCollections).toEqual([{ name: "a" }, { name: "b" }, { name: "c" }]);
    expect(allDocuments).toEqual([{ id: "doc-1" }, { id: "doc-2" }, { id: "doc-3" }]);
  });
});
