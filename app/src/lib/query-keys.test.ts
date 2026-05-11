import { describe, expect, it } from "vitest";
import { queryKeys } from "./query-keys";

describe("queryKeys", () => {
  it("keeps collection and document keys stable", () => {
    expect(queryKeys.collections.one({ name: "docs" })).toEqual([
      "collections",
      "detail",
      { name: "docs" },
    ]);
    expect(queryKeys.documents.chunks({ collection: "docs", id: "doc_1" })).toEqual([
      "documents",
      "chunks",
      { collection: "docs", id: "doc_1" },
    ]);
  });

  it("uses all sentinels for optional connector filters", () => {
    expect(queryKeys.connectors.googleSources()).toEqual([
      "connectors",
      "google",
      "sources",
      { collection: "all" },
    ]);
    expect(queryKeys.connectors.googleSyncJobs()).toEqual([
      "connectors",
      "google",
      "sync-jobs",
      { collection: "all", sourceId: "all" },
    ]);
  });

  it("builds every top-level cache key shape", () => {
    const filters = { collection: "docs", status: "2xx" };

    expect(queryKeys.auth.all()).toEqual(["auth"]);
    expect(queryKeys.auth.setupStatus()).toEqual(["auth", "setup-status"]);
    expect(queryKeys.auth.session()).toEqual(["auth", "session"]);
    expect(queryKeys.apiKeys()).toEqual(["api-keys"]);
    expect(queryKeys.backups()).toEqual(["backups"]);
    expect(queryKeys.access.logs(filters)).toEqual(["access", "logs", filters]);
    expect(queryKeys.access.overview({ windowDays: 30 })).toEqual([
      "access",
      "overview",
      { windowDays: 30 },
    ]);
    expect(queryKeys.audit.recent()).toEqual(["audit", "recent"]);
    expect(queryKeys.mcpServers()).toEqual(["mcp-servers"]);
    expect(queryKeys.webhooks()).toEqual(["webhooks"]);
    expect(queryKeys.embeddingPresets()).toEqual(["embedding-presets"]);
    expect(queryKeys.preferences()).toEqual(["preferences"]);
    expect(queryKeys.instanceSettings()).toEqual(["instance-settings"]);
    expect(queryKeys.connectors.googleConfig()).toEqual(["connectors", "google", "config"]);
    expect(queryKeys.connectors.googleAccount()).toEqual(["connectors", "google", "account"]);
    expect(queryKeys.connectors.googleFilesRoot()).toEqual(["connectors", "google", "files"]);
    expect(
      queryKeys.connectors.googleFiles({ pageToken: "next", parentId: "folder", query: "pdf" }),
    ).toEqual([
      "connectors",
      "google",
      "files",
      { pageToken: "next", parentId: "folder", query: "pdf" },
    ]);
    expect(queryKeys.connectors.googleSources({ collection: "docs" })).toEqual([
      "connectors",
      "google",
      "sources",
      { collection: "docs" },
    ]);
    expect(queryKeys.connectors.googleSyncJobs({ collection: "docs", sourceId: "source" })).toEqual(
      ["connectors", "google", "sync-jobs", { collection: "docs", sourceId: "source" }],
    );
    expect(queryKeys.chat.list()).toEqual(["chat", "list"]);
    expect(queryKeys.chat.detail({ id: null })).toEqual(["chat", "detail", { id: null }]);
    expect(queryKeys.collections.all()).toEqual(["collections"]);
    expect(queryKeys.collections.stats({ name: "docs" })).toEqual([
      "collections",
      "stats",
      { name: "docs" },
    ]);
    expect(queryKeys.documents.list({ collection: "docs" })).toEqual([
      "documents",
      "list",
      { collection: "docs" },
    ]);
    expect(queryKeys.documents.one({ collection: "docs", id: "doc" })).toEqual([
      "documents",
      "detail",
      { collection: "docs", id: "doc" },
    ]);
    expect(queryKeys.documents.batchStatus({ collection: "docs", ids: "a,b" })).toEqual([
      "documents",
      "batch-status",
      { collection: "docs", ids: "a,b" },
    ]);
    expect(queryKeys.documents.uploadSession({ collection: "docs", id: null })).toEqual([
      "documents",
      "upload-session",
      { collection: "docs", id: null },
    ]);
    expect(queryKeys.platform.stats()).toEqual(["platform", "stats"]);
    expect(queryKeys.platform.readiness()).toEqual(["platform", "readiness"]);
    expect(queryKeys.platform.embeddingModels()).toEqual(["platform", "embedding-models"]);
    expect(queryKeys.usage({ windowDays: 30 })).toEqual(["usage", { windowDays: 30 }]);
  });
});
