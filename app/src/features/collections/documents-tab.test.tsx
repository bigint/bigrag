import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { DocumentsTab } from "./documents-tab";

type UploadStoreMock = {
  activeSessionIds: Record<string, string>;
  clearActiveSessionId: (collection: string) => void;
  setActiveSessionId: (collection: string, sessionId: string) => void;
};

const uploadStore = vi.hoisted<UploadStoreMock>(() => ({
  activeSessionIds: {},
  clearActiveSessionId: vi.fn(),
  setActiveSessionId: vi.fn(),
}));

vi.mock("@tanstack/react-router", async () => {
  const React = await import("react");
  return {
    Link: ({
      children,
      href,
      params: _params,
      to,
      ...props
    }: {
      children?: ReactNode;
      className?: string;
      href?: string;
      params?: unknown;
      to?: string;
    }) => React.createElement("a", { ...props, href: href ?? to }, children),
  };
});

vi.mock("@/features/collections/upload-session-store", () => ({
  useUploadSessionStore: <T,>(selector: (state: UploadStoreMock) => T) => selector(uploadStore),
}));

vi.mock("@/hooks/use-collections", () => ({
  useCollection: () => ({ data: { metadata: {} } }),
}));

vi.mock("@/hooks/use-documents", () => ({
  useCancelUploadSession: () => ({ isPending: false, mutate: vi.fn() }),
  useDeleteDocument: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useDocuments: () => ({ data: { documents: [], total: 0 }, isPending: false }),
  useUploadSession: () => ({ data: undefined, streaming: false }),
  useUploadSessionDocuments: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

vi.mock("@/hooks/use-platform", () => ({
  usePlatformStats: () => ({
    data: {
      collections: 1,
      documents: {
        failed: 0,
        pending: 0,
        processing: 0,
        ready: 0,
        total: 0,
        total_chunks: 0,
        total_size_bytes: 0,
        total_tokens: 0,
      },
      queue: {
        completed: 0,
        failed: 0,
        pending: 0,
        processing: 0,
        queued: 0,
      },
      webhooks: 0,
      workers: {
        heartbeat_age_seconds: null,
        heartbeat_at: null,
        online: false,
      },
    },
  }),
}));

describe("DocumentsTab", () => {
  it("shows worker offline copy and disables upload actions", () => {
    const html = renderToStaticMarkup(<DocumentsTab name="docs" />);

    expect(html).toContain("bigrag-worker is offline");
    expect(html).toContain("Worker offline");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>[\s\S]*Files/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>[\s\S]*Folder/);
  });
});
