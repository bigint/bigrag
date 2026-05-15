import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { OverviewPage } from "./overview-page";

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

vi.mock("@/hooks/use-access-logs", () => ({
  useAccessOverview: () => ({ data: undefined, isPending: false }),
}));

vi.mock("@/hooks/use-auth", () => ({
  useSession: () => ({
    data: {
      user: {
        display_name: "Asha Rao",
        email: "asha@example.com",
        role: "member",
      },
    },
  }),
}));

vi.mock("@/hooks/use-collections", () => ({
  useCollections: () => ({
    data: {
      collections: [
        {
          default_search_mode: "hybrid",
          description: "Runbooks",
          document_count: 3,
          embedding_model: "text-embedding-3-small",
          id: "col_1",
          name: "ops",
          updated_at: "2026-05-15T00:00:00Z",
        },
      ],
    },
  }),
}));

vi.mock("@/hooks/use-platform", () => ({
  usePlatformStats: () => ({
    data: {
      collections: 1,
      documents: {
        failed: 0,
        pending: 0,
        processing: 1,
        ready: 3,
        total: 4,
        total_chunks: 120,
        total_size_bytes: 4096,
        total_tokens: 2850,
      },
      queue: {
        completed: 0,
        failed: 0,
        pending: 3,
        processing: 1,
        queued: 4,
      },
      webhooks: 0,
      workers: {
        heartbeat_age_seconds: 180,
        heartbeat_at: "2026-05-15T12:00:00+00:00",
        online: false,
      },
    },
    isPending: false,
  }),
  useReadiness: () => ({
    data: {
      embedding: true,
      postgres: true,
      qdrant: true,
      redis: true,
      status: "ok",
      vector_store: true,
      vector_store_provider: "qdrant",
      version: "test",
    },
  }),
}));

describe("OverviewPage", () => {
  it("renders stored token totals as a first-class dashboard metric", () => {
    const html = renderToStaticMarkup(<OverviewPage />);

    expect(html).toContain("Tokens stored");
    expect(html).toContain("2,850");
    expect(html).toContain("Across indexed documents");
  });

  it("surfaces worker health and blocked queue work", () => {
    const html = renderToStaticMarkup(<OverviewPage />);

    expect(html).toContain("Worker");
    expect(html).toContain("bigrag-worker is offline");
    expect(html).toContain("Pending uploads, backups, webhooks, and Drive syncs cannot drain");
  });
});
