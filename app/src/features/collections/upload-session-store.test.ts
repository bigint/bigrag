import { beforeEach, describe, expect, it, vi } from "vitest";
import { useUploadSessionStore } from "@/features/collections/upload-session-store";

const createStorage = (): Storage => {
  let data: Record<string, string> = {};
  return {
    get length() {
      return Object.keys(data).length;
    },
    clear: vi.fn(() => {
      data = {};
    }),
    getItem: vi.fn((key: string) => data[key] ?? null),
    key: vi.fn((index: number) => Object.keys(data)[index] ?? null),
    removeItem: vi.fn((key: string) => {
      delete data[key];
    }),
    setItem: vi.fn((key: string, value: string) => {
      data[key] = value;
    }),
  };
};

const resetUploadSessionStore = () => {
  useUploadSessionStore.setState({ activeSessionIds: {} });
};

describe("useUploadSessionStore", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", createStorage());
    globalThis.localStorage.clear();
    resetUploadSessionStore();
  });

  it("persists and clears active upload sessions per collection", () => {
    useUploadSessionStore.getState().setActiveSessionId("docs", "session-1");
    useUploadSessionStore.getState().setActiveSessionId("support", "session-2");

    expect(useUploadSessionStore.getState().activeSessionIds).toEqual({
      docs: "session-1",
      support: "session-2",
    });
    expect(globalThis.localStorage.getItem("bigrag:upload-sessions")).toContain("session-1");

    useUploadSessionStore.getState().clearActiveSessionId("docs");

    expect(useUploadSessionStore.getState().activeSessionIds).toEqual({
      support: "session-2",
    });
    expect(globalThis.localStorage.getItem("bigrag:upload-sessions")).not.toContain("session-1");
  });

  it("migrates legacy per-collection localStorage keys", () => {
    globalThis.localStorage.setItem("bigrag:upload-session:docs", "legacy-session");

    useUploadSessionStore.getState().migrateLegacyUploadSession("docs");

    expect(useUploadSessionStore.getState().activeSessionIds.docs).toBe("legacy-session");
    expect(globalThis.localStorage.getItem("bigrag:upload-session:docs")).toBeNull();
  });

  it("does not overwrite existing persisted sessions during legacy migration", () => {
    useUploadSessionStore.getState().setActiveSessionId("docs", "current-session");
    globalThis.localStorage.setItem("bigrag:upload-session:docs", "legacy-session");

    useUploadSessionStore.getState().migrateLegacyUploadSession("docs");

    expect(useUploadSessionStore.getState().activeSessionIds.docs).toBe("current-session");
    expect(globalThis.localStorage.getItem("bigrag:upload-session:docs")).toBeNull();
  });
});
