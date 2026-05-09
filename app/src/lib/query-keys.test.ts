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
});
