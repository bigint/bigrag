import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { ServerTab } from "./server-tab";

vi.mock("@/hooks/use-platform", () => ({
  usePlatformStats: () => ({
    data: {
      collections: 1,
      documents: {
        failed: 0,
        pending: 1,
        processing: 0,
        ready: 2,
        total: 3,
        total_chunks: 20,
        total_size_bytes: 2048,
        total_tokens: 500,
      },
      queue: {
        completed: 2,
        dead_lettered: 1,
        failed: 0,
        pending: 4,
        processing: 0,
        queued: 4,
        retrying: 1,
        stale_processing: 0,
      },
      queue_health: {
        reasons: ["worker_offline_with_active_queue", "dead_lettered_jobs", "retrying_jobs"],
        status: "down",
      },
      status: "down",
      webhooks: 0,
      workers: {
        heartbeat_age_seconds: 181,
        heartbeat_at: "2026-05-15T11:57:00+00:00",
        online: false,
        status: "offline",
      },
    },
  }),
  useReadiness: () => ({
    data: {
      embedding: false,
      embedding_error: "auth_failed",
      embedding_source: "settings",
      postgres: true,
      qdrant: true,
      redis: false,
      redis_error: "unreachable",
      status: "degraded",
      vector_store: true,
      vector_store_provider: "qdrant",
      version: "test",
    },
  }),
}));

describe("ServerTab", () => {
  it("renders dependency errors, worker heartbeat, and queue health", () => {
    const html = renderToStaticMarkup(<ServerTab />);

    expect(html).toContain("Redis");
    expect(html).toContain("unreachable");
    expect(html).toContain("Worker and queue");
    expect(html).toContain("worker offline with active queue");
    expect(html).toContain("Dead-lettered");
    expect(html).toContain("heartbeat 3 minutes ago");
  });
});
