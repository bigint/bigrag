import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { WebhooksPage } from "./_dashboard.webhooks";

vi.mock("@/hooks/use-webhooks", () => ({
  useCreateWebhook: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useDeleteWebhook: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useTestWebhook: () => ({ mutate: vi.fn() }),
  useWebhooks: () => ({ data: { webhooks: [] }, error: null, isPending: false }),
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
        heartbeat_age_seconds: 240,
        heartbeat_at: "2026-05-15T12:00:00Z",
        online: false,
      },
    },
  }),
}));

describe("WebhooksPage", () => {
  it("warns about offline worker delivery without blocking configuration", () => {
    const html = renderToStaticMarkup(<WebhooksPage />);

    expect(html).toContain("Document-event deliveries require bigrag-worker.");
    expect(html).toContain("Add Webhook");
    expect(html).not.toMatch(/Add Webhook<\/button>[\s\S]*disabled=""/);
  });
});
