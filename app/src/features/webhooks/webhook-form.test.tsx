import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { getWorkerAvailability } from "@/features/workers/worker-status";
import { WebhookForm } from "./webhook-form";

vi.mock("@/hooks/use-webhooks", () => ({
  useCreateWebhook: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

describe("WebhookForm", () => {
  it("warns that document event deliveries need the worker without blocking creation", () => {
    const workerAvailability = getWorkerAvailability({
      workers: {
        heartbeat_age_seconds: 121,
        heartbeat_at: "2026-05-15T12:00:00Z",
        online: false,
      },
    });
    const html = renderToStaticMarkup(
      <WebhookForm
        onClose={vi.fn()}
        onCreated={vi.fn()}
        open
        workerAvailability={workerAvailability}
      />,
    );

    expect(html).toContain("Document-event deliveries require bigrag-worker.");
    expect(html).toContain("Add Webhook");
    expect(html).not.toMatch(/type="submit"[^>]*disabled=""/);
  });
});
