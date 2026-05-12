import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

vi.mock("react", () => ({
  useEffect: vi.fn((fn: () => unknown) => fn()),
  useMemo: vi.fn((fn: () => unknown) => fn()),
  useRef: vi.fn((value: unknown) => ({ current: value })),
  useState: vi.fn((value: unknown) => [value, vi.fn()]),
}));

vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn((options) => options),
  useQuery: vi.fn((options) => options),
  useQueryClient: vi.fn(),
}));

vi.mock("@/hooks/use-sse-snapshot-query", () => ({
  useSseSnapshotQuery: vi.fn((options) => options),
}));

vi.mock("@/lib/api", () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    postForm: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

const queryClient = {
  cancelQueries: vi.fn(),
  clear: vi.fn(),
  fetchQuery: vi.fn(),
  getQueryData: vi.fn(),
  invalidateQueries: vi.fn(),
  setQueryData: vi.fn(),
};

const mutationOptions = <T = unknown>() => vi.mocked(useMutation).mock.results.at(-1)?.value as T;
const queryOptions = <T = unknown>() => vi.mocked(useQuery).mock.results.at(-1)?.value as T;
const sseOptions = <T = unknown>() =>
  vi.mocked(useSseSnapshotQuery).mock.results.at(-1)?.value as T;

beforeEach(() => {
  vi.mocked(useQueryClient).mockReturnValue(queryClient as never);
});

afterEach(() => {
  vi.clearAllMocks();
  queryClient.getQueryData.mockReset();
});

describe("admin app hooks", () => {
  it("builds access log SSE options with compact filters", async () => {
    const { useAccessLogs, useAccessOverview } = await import("./use-access-logs");

    useAccessOverview(true, 14);
    expect(sseOptions()).toMatchObject({
      enabled: true,
      path: "v1/admin/realtime/access/overview?window_days=14",
      queryKey: queryKeys.access.overview({ windowDays: 14 }),
    });
    await sseOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/admin/access/overview", {
      window_days: 14,
    });

    useAccessLogs({
      action: "",
      collection: "docs",
      limit: 25,
      status_family: "2xx",
      success: false,
    });
    expect(sseOptions()).toMatchObject({
      path: "v1/admin/realtime/access/logs?collection=docs&limit=25&status_family=2xx&success=false",
      queryKey: queryKeys.access.logs({
        collection: "docs",
        limit: 25,
        status_family: "2xx",
        success: false,
      }),
    });
    await sseOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/admin/access/logs", {
      collection: "docs",
      limit: 25,
      status_family: "2xx",
      success: false,
    });
  });

  it("wires auth queries and session mutations", async () => {
    const { useChangePassword, useLogin, useLogout, useLogoutAll, useSession, useSetup } =
      await import("./use-auth");

    useSession();
    vi.mocked(apiClient.get).mockRejectedValueOnce({ response: { status: 401 } });
    await expect(queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn()).resolves.toBeNull();
    vi.mocked(apiClient.get).mockRejectedValueOnce({ response: { status: 500 } });
    await expect(
      queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn(),
    ).rejects.toMatchObject({
      response: { status: 500 },
    });

    useLogin();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      email: "admin@example.com",
      password: "secret",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/auth/login", {
      email: "admin@example.com",
      password: "secret",
    });
    mutationOptions<{ onSuccess: (data: unknown) => void }>().onSuccess({ user: { id: "u1" } });
    expect(queryClient.setQueryData).toHaveBeenCalledWith(queryKeys.auth.session(), {
      user: { id: "u1" },
    });
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.auth.all() });

    useLogout();
    mutationOptions<{ onSuccess: () => void }>().onSuccess();
    expect(queryClient.clear).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith("Signed out");

    useLogoutAll();
    mutationOptions<{ onSuccess: () => void }>().onSuccess();
    expect(toast.success).toHaveBeenCalledWith("Signed out of all devices");

    useSetup();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      display_name: "Admin",
      email: "admin@example.com",
      password: "secret",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/auth/setup", {
      display_name: "Admin",
      email: "admin@example.com",
      password: "secret",
    });

    useChangePassword();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      current_password: "old",
      new_password: "new",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/auth/password", {
      current_password: "old",
      new_password: "new",
    });
  });

  it("wires API key CRUD hooks", async () => {
    const { useApiKeys, useCreateApiKey, useDeleteApiKey, useUpdateApiKey } = await import(
      "./use-api-keys"
    );

    useApiKeys();
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/admin/api-keys");

    useCreateApiKey();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      name: "ci",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/api-keys", { name: "ci" });

    useUpdateApiKey();
    await mutationOptions<{
      mutationFn: (body: { id: string; name: string }) => Promise<unknown>;
    }>().mutationFn({
      id: "key_1",
      name: "prod",
    });
    expect(apiClient.patch).toHaveBeenLastCalledWith("v1/admin/api-keys/key_1", { name: "prod" });

    useDeleteApiKey();
    await mutationOptions<{ mutationFn: (id: string) => Promise<unknown> }>().mutationFn("key_1");
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/admin/api-keys/key_1");
    mutationOptions<{ onSuccess: () => void }>().onSuccess();
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.apiKeys() });
    expect(toast.success).toHaveBeenCalledWith("Key revoked");
  });

  it("wires collection queries and mutations with encoded names", async () => {
    const {
      useCollection,
      useCollectionStats,
      useCollections,
      useCreateCollection,
      useDeleteCollection,
      useTruncateCollection,
      useUpdateCollection,
    } = await import("./use-collections");

    useCollections();
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/collections", { limit: 200 });

    useCollection("team docs");
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/collections/team%20docs");

    useCollectionStats("team docs");
    expect(sseOptions()).toMatchObject({
      path: "v1/admin/realtime/collections/team%20docs/stats",
      queryKey: queryKeys.collections.stats({ name: "team docs" }),
    });

    useCreateCollection();
    mutationOptions<{ onSuccess: (collection: { name: string }) => void }>().onSuccess({
      name: "docs",
    });
    expect(toast.success).toHaveBeenCalledWith('Collection "docs" created');

    useUpdateCollection("team docs");
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      description: "Updated",
    });
    expect(apiClient.put).toHaveBeenLastCalledWith("v1/collections/team%20docs", {
      description: "Updated",
    });

    useDeleteCollection();
    await mutationOptions<{ mutationFn: (name: string) => Promise<unknown> }>().mutationFn(
      "team docs",
    );
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/collections/team%20docs");

    useTruncateCollection("team docs");
    await mutationOptions<{ mutationFn: () => Promise<unknown> }>().mutationFn();
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/collections/team%20docs/truncate");
  });

  it("wires document queries, uploads, batch progress, and mutations", async () => {
    const {
      useBatchDocumentProgress,
      useCancelUploadSession,
      useChunks,
      useDeleteDocument,
      useDocument,
      useDocuments,
      useReprocessDocument,
      useUploadDocuments,
      useUploadSession,
      useUploadSessionDocuments,
    } = await import("./use-documents");

    useDocuments("team docs", "ready");
    expect(sseOptions()).toMatchObject({
      enabled: true,
      path: "v1/admin/realtime/collections/team%20docs/documents?limit=100&status=ready",
    });
    await sseOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/collections/team%20docs/documents", {
      limit: 100,
      status: "ready",
    });

    useDocument("team docs", "doc_1");
    expect(
      sseOptions<{ closeWhen: (doc: { status: string }) => boolean }>().closeWhen({
        status: "ready",
      }),
    ).toBe(true);

    useChunks("team docs", "doc_1");
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith(
      "v1/collections/team%20docs/documents/doc_1/chunks",
      { limit: 200 },
    );

    useUploadDocuments("team docs");
    await mutationOptions<{ mutationFn: (files: File[]) => Promise<unknown> }>().mutationFn([
      new File(["hello"], "a.txt"),
    ]);
    expect(apiClient.postForm).toHaveBeenLastCalledWith(
      "v1/collections/team%20docs/documents/batch/upload",
      expect.any(FormData),
    );
    mutationOptions<{ onSuccess: (res: { total: number }) => void }>().onSuccess({ total: 2 });
    expect(toast.success).toHaveBeenCalledWith("Queued 2 documents for ingestion");

    useUploadSession("team docs", "session_1");
    expect(
      sseOptions<{ closeWhen: (session: { status: string }) => boolean }>().closeWhen({
        status: "canceled",
      }),
    ).toBe(true);

    const started = vi.fn();
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({ id: "session_1" })
      .mockResolvedValueOnce({ id: "session_1", uploaded_files: 1 });
    vi.mocked(apiClient.postForm).mockResolvedValueOnce({});
    useUploadSessionDocuments("team docs", { onSessionStart: started });
    await expect(
      mutationOptions<{ mutationFn: (files: File[]) => Promise<unknown> }>().mutationFn([
        new File(["hello"], "a.txt", { lastModified: 10 }),
      ]),
    ).resolves.toMatchObject({ errors: [], session: { id: "session_1" } });
    expect(started).toHaveBeenCalledWith({ id: "session_1" });
    expect(apiClient.post).toHaveBeenNthCalledWith(
      1,
      "v1/collections/team%20docs/upload-sessions",
      { metadata: {}, total_bytes: 5, total_files: 1 },
    );
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      "v1/collections/team%20docs/upload-sessions/session_1/complete",
    );

    useCancelUploadSession("team docs");
    await mutationOptions<{ mutationFn: (sessionId: string) => Promise<unknown> }>().mutationFn(
      "session_1",
    );
    expect(apiClient.post).toHaveBeenLastCalledWith(
      "v1/collections/team%20docs/upload-sessions/session_1/cancel",
    );

    vi.mocked(useSseSnapshotQuery).mockReturnValueOnce({
      data: {
        documents: [
          {
            chunk_count: 3,
            error_message: null,
            id: "doc_1",
            progress: null,
            status: "ready",
          },
        ],
      },
      streaming: true,
    } as never);
    const progress = useBatchDocumentProgress("team docs", [
      {
        chunk_count: 0,
        error_message: null,
        file_size: 10,
        file_type: "text/plain",
        filename: "a.txt",
        id: "doc_1",
        progress: null,
        status: "processing",
      } as never,
    ]);
    expect(progress).toMatchObject({
      completedCount: 1,
      done: true,
      failedCount: 0,
      progress: 100,
      total: 1,
    });

    useDeleteDocument("team docs");
    await mutationOptions<{ mutationFn: (docId: string) => Promise<unknown> }>().mutationFn(
      "doc_1",
    );
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/collections/team%20docs/documents/doc_1");

    useReprocessDocument("team docs");
    await mutationOptions<{ mutationFn: (docId: string) => Promise<unknown> }>().mutationFn(
      "doc_1",
    );
    expect(apiClient.post).toHaveBeenLastCalledWith(
      "v1/collections/team%20docs/documents/doc_1/reprocess",
    );
  });

  it("wires Google Drive connector hooks and cache updates", async () => {
    const {
      useCreateGoogleSource,
      useDeleteGoogleSource,
      useDisconnectGoogle,
      useGoogleDriveFiles,
      useGoogleSources,
      useGoogleSyncJobs,
      useSyncGoogleSource,
      useUpdateGoogleConnectorConfig,
      useUpdateGoogleSource,
    } = await import("./use-google-drive");

    useUpdateGoogleConnectorConfig();
    mutationOptions<{ onSuccess: () => void }>().onSuccess();
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: queryKeys.connectors.googleConfig(),
    });

    useGoogleDriveFiles({
      enabled: true,
      pageToken: "next",
      parentId: "root",
      query: "pdf",
    });
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/connectors/google/files", {
      page_token: "next",
      parent_id: "root",
      query: "pdf",
    });

    useGoogleSources("docs");
    expect(sseOptions()).toMatchObject({
      path: "v1/admin/realtime/google/sources?collection=docs",
      queryKey: queryKeys.connectors.googleSources({ collection: "docs" }),
    });

    useGoogleSyncJobs({ collection: "docs", limit: 5, sourceId: "source_1" });
    expect(sseOptions()).toMatchObject({
      path: "v1/admin/realtime/google/sync-jobs?limit=5&collection=docs&source_id=source_1",
      queryKey: queryKeys.connectors.googleSyncJobs({ collection: "docs", sourceId: "source_1" }),
    });

    useCreateGoogleSource("docs");
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      root_id: "root",
      root_mime_type: "folder",
      root_name: "Drive",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/connectors/google/sources", {
      collection_name: "docs",
      root_id: "root",
      root_mime_type: "folder",
      root_name: "Drive",
    });
    mutationOptions<{ onSuccess: (source: { id: string }) => void }>().onSuccess({
      id: "source_1",
    });
    expect(queryClient.setQueryData).toHaveBeenCalledWith(
      queryKeys.connectors.googleSources({ collection: "docs" }),
      expect.any(Function),
    );

    useSyncGoogleSource("docs");
    mutationOptions<{ onSuccess: (job: unknown, sourceId: string) => void }>().onSuccess(
      {},
      "source_1",
    );
    expect(toast.success).toHaveBeenCalledWith("Google Drive sync queued");

    useUpdateGoogleSource("docs");
    await mutationOptions<{
      mutationFn: (body: { sourceId: string; body: unknown }) => Promise<unknown>;
    }>().mutationFn({
      body: { schedule_enabled: true },
      sourceId: "source_1",
    });
    expect(apiClient.patch).toHaveBeenLastCalledWith("v1/connectors/google/sources/source_1", {
      schedule_enabled: true,
    });

    useDeleteGoogleSource("docs");
    await mutationOptions<{ mutationFn: (sourceId: string) => Promise<unknown> }>().mutationFn(
      "source_1",
    );
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/connectors/google/sources/source_1");

    useDisconnectGoogle();
    await mutationOptions<{ mutationFn: () => Promise<unknown> }>().mutationFn();
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/connectors/google/disconnect");
  });

  it("wires admin resource mutation hooks", async () => {
    const { useBackups, useStartBackup } = await import("./use-backups");
    const { useDeleteChatConversation } = await import("./use-chat");
    const { useCreateEmbeddingPreset, useDeleteEmbeddingPreset, useUpdateEmbeddingPreset } =
      await import("./use-embedding-presets");
    const {
      usePurgeEmbeddingCache,
      useResetInstanceSettings,
      useTestInstanceSettings,
      useUpdateInstanceSettings,
    } = await import("./use-instance-settings");
    const { useCreateMcpServer, useDeleteMcpServer, useRotateMcpServer } = await import(
      "./use-mcp-servers"
    );
    const { useRunQuery } = await import("./use-query");
    const { useCreateWebhook, useDeleteWebhook, useTestWebhook } = await import("./use-webhooks");

    useBackups();
    expect(sseOptions()).toMatchObject({ path: "v1/admin/realtime/backups" });

    useStartBackup();
    await mutationOptions<{
      mutationFn: (body: { label?: string }) => Promise<unknown>;
    }>().mutationFn({});
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/backups", { label: "" });

    useDeleteChatConversation();
    await mutationOptions<{ mutationFn: (id: string) => Promise<unknown> }>().mutationFn("chat_1");
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/chat/chat_1");

    useCreateEmbeddingPreset();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      name: "small",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/embedding-presets", {
      name: "small",
    });

    useUpdateEmbeddingPreset();
    await mutationOptions<{
      mutationFn: (body: { id: string; model: string }) => Promise<unknown>;
    }>().mutationFn({
      id: "preset_1",
      model: "large",
    });
    expect(apiClient.patch).toHaveBeenLastCalledWith("v1/admin/embedding-presets/preset_1", {
      model: "large",
    });

    useDeleteEmbeddingPreset();
    await mutationOptions<{ mutationFn: (id: string) => Promise<unknown> }>().mutationFn(
      "preset_1",
    );
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/admin/embedding-presets/preset_1");

    useUpdateInstanceSettings();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      values: { key: "value" },
    });
    expect(apiClient.put).toHaveBeenLastCalledWith("v1/admin/settings", {
      values: { key: "value" },
    });

    useTestInstanceSettings();
    mutationOptions<{ onSuccess: (result: { message: string }) => void }>().onSuccess({
      message: "ok",
    });
    expect(toast.success).toHaveBeenCalledWith("ok");

    useResetInstanceSettings();
    await mutationOptions<{ mutationFn: (keys: string[]) => Promise<unknown> }>().mutationFn([
      "openai_key",
    ]);
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/settings/reset", {
      keys: ["openai_key"],
    });

    usePurgeEmbeddingCache();
    await mutationOptions<{ mutationFn: () => Promise<unknown> }>().mutationFn();
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/settings/embedding-cache/purge");

    useCreateMcpServer();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      server_name: "docs",
      title: "Docs",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/mcp-servers", {
      server_name: "docs",
      title: "Docs",
    });

    useRotateMcpServer();
    await mutationOptions<{ mutationFn: (id: string) => Promise<unknown> }>().mutationFn("mcp_1");
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/mcp-servers/mcp_1/rotate");

    useDeleteMcpServer();
    await mutationOptions<{ mutationFn: (id: string) => Promise<unknown> }>().mutationFn("mcp_1");
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/admin/mcp-servers/mcp_1");

    useRunQuery("team docs");
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      query: "what changed?",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/collections/team%20docs/query", {
      query: "what changed?",
    });

    useCreateWebhook();
    await mutationOptions<{ mutationFn: (body: unknown) => Promise<unknown> }>().mutationFn({
      events: ["document.ready"],
      url: "https://example.com",
    });
    expect(apiClient.post).toHaveBeenLastCalledWith("v1/admin/webhooks", {
      events: ["document.ready"],
      url: "https://example.com",
    });

    useDeleteWebhook();
    await mutationOptions<{ mutationFn: (id: string) => Promise<unknown> }>().mutationFn("wh_1");
    expect(apiClient.delete).toHaveBeenLastCalledWith("v1/admin/webhooks/wh_1");

    useTestWebhook();
    mutationOptions<{
      onSuccess: (res: { error?: string; status: string; status_code: number }) => void;
    }>().onSuccess({
      status: "failed",
      status_code: 500,
    });
    expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/^Test failed . unknown$/));
  });

  it("wires platform and preference hooks", async () => {
    const { useEmbeddingModels, usePlatformStats, useReadiness } = await import("./use-platform");
    const { usePreferences, useUpdatePreferences } = await import("./use-preferences");

    usePlatformStats();
    expect(sseOptions()).toMatchObject({
      path: "v1/admin/realtime/platform/stats",
      queryKey: queryKeys.platform.stats(),
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ready: true }), { status: 503 })),
    );
    useReadiness();
    await expect(sseOptions<{ queryFn: () => Promise<unknown> }>().queryFn()).resolves.toEqual({
      ready: true,
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 500 })),
    );
    await expect(sseOptions<{ queryFn: () => Promise<unknown> }>().queryFn()).rejects.toThrow(
      "readiness probe: HTTP 500",
    );
    vi.unstubAllGlobals();

    useEmbeddingModels();
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/embeddings/models");

    usePreferences();
    await queryOptions<{ queryFn: () => Promise<unknown> }>().queryFn();
    expect(apiClient.get).toHaveBeenLastCalledWith("v1/auth/preferences");

    queryClient.getQueryData.mockReturnValueOnce({
      data: { chat: { model: "old", openai_key: "hidden" } },
    });
    useUpdatePreferences();
    const context = await mutationOptions<{
      onMutate: (patch: { chat: { model: string; openai_key: string } }) => Promise<unknown>;
    }>().onMutate({
      chat: { model: "new", openai_key: "secret" },
    });
    expect(context).toEqual({
      previous: { data: { chat: { model: "old", openai_key: "hidden" } } },
    });
    const updater = queryClient.setQueryData.mock.calls.at(-1)?.[1] as (old: {
      data: { chat: { model: string; openai_key: string } };
    }) => unknown;
    expect(updater({ data: { chat: { model: "old", openai_key: "hidden" } } })).toEqual({
      data: { chat: { model: "new", openai_key: "hidden" } },
    });
  });
});
