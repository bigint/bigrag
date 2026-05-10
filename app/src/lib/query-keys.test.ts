import { describe, expect, it } from "vitest";
import { queryKeys } from "./query-keys";

describe("queryKeys", () => {
  it("keeps collection and document keys stable", () => {
    expect(queryKeys.collections.one("docs")).toEqual(["collections", "docs"]);
    expect(queryKeys.documents.chunks("docs", "doc_1")).toEqual([
      "documents",
      "docs",
      "doc_1",
      "chunks",
    ]);
  });

  it("uses all sentinels for optional connector filters", () => {
    expect(queryKeys.connectors.googleSources()).toEqual([
      "connectors",
      "google",
      "sources",
      "all",
    ]);
    expect(queryKeys.connectors.googleSyncJobs()).toEqual([
      "connectors",
      "google",
      "sync-jobs",
      "all",
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
    expect(queryKeys.access.overview(30)).toEqual(["access", "overview", 30]);
    expect(queryKeys.mcpServers()).toEqual(["mcp-servers"]);
    expect(queryKeys.webhooks()).toEqual(["webhooks"]);
    expect(queryKeys.embeddingPresets()).toEqual(["embedding-presets"]);
    expect(queryKeys.preferences()).toEqual(["preferences"]);
    expect(queryKeys.instanceSettings()).toEqual(["instance-settings"]);
    expect(queryKeys.connectors.googleConfig()).toEqual(["connectors", "google", "config"]);
    expect(queryKeys.connectors.googleAccount()).toEqual(["connectors", "google", "account"]);
    expect(queryKeys.connectors.googleFiles("folder", "pdf", "next")).toEqual([
      "connectors",
      "google",
      "files",
      "folder",
      "pdf",
      "next",
    ]);
    expect(queryKeys.connectors.googleSources("docs")).toEqual([
      "connectors",
      "google",
      "sources",
      "docs",
    ]);
    expect(queryKeys.connectors.googleSyncJobs("source")).toEqual([
      "connectors",
      "google",
      "sync-jobs",
      "source",
    ]);
    expect(queryKeys.chat.list()).toEqual(["chat", "list"]);
    expect(queryKeys.chat.detail(null)).toEqual(["chat", "detail", null]);
    expect(queryKeys.collections.all()).toEqual(["collections"]);
    expect(queryKeys.collections.stats("docs")).toEqual(["collections", "docs", "stats"]);
    expect(queryKeys.documents.list("docs")).toEqual(["documents", "docs"]);
    expect(queryKeys.documents.one("docs", "doc")).toEqual(["documents", "docs", "doc"]);
    expect(queryKeys.documents.batchStatus("docs", "a,b")).toEqual([
      "documents",
      "docs",
      "batch-status",
      "a,b",
    ]);
    expect(queryKeys.documents.uploadSession("docs", null)).toEqual([
      "documents",
      "docs",
      "upload-session",
      null,
    ]);
    expect(queryKeys.platform.stats()).toEqual(["platform", "stats"]);
    expect(queryKeys.platform.readiness()).toEqual(["platform", "readiness"]);
    expect(queryKeys.platform.embeddingModels()).toEqual(["platform", "embedding-models"]);
  });
});
