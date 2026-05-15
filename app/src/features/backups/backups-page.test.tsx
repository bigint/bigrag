import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { BackupsPage } from "./backups-page";

const startBackup = vi.hoisted(() => vi.fn());

vi.mock("@/features/settings/tabs/instance-settings-tab", () => ({
  InstanceSettingsTab: () => <section>Backup settings</section>,
}));

vi.mock("@/hooks/use-backups", () => ({
  useBackups: () => ({
    data: { jobs: [] },
    streaming: true,
  }),
  useStartBackup: () => ({
    isPending: false,
    mutate: startBackup,
  }),
}));

vi.mock("@/hooks/use-instance-settings", () => ({
  useInstanceSettings: () => ({
    data: {
      values: {
        backup_s3_bucket: {
          has_value: true,
          key: "backup_s3_bucket",
          source: "database",
          updated_at: null,
          updated_by: null,
          value: "bigrag-backups",
        },
      },
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
        processing: 0,
        ready: 1,
        total: 1,
        total_chunks: 2,
        total_size_bytes: 512,
        total_tokens: 128,
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
        heartbeat_age_seconds: 180,
        heartbeat_at: "2026-05-15T12:00:00+00:00",
        online: false,
      },
    },
  }),
}));

describe("BackupsPage", () => {
  it("does not render the realtime transport badge in the page header", () => {
    const html = renderToStaticMarkup(<BackupsPage />);

    expect(html).toContain("Backups");
    expect(html).toContain("Readable backups");
    expect(html).not.toContain(">live<");
    expect(html).not.toContain(">polling<");
  });

  it("blocks backup starts while the worker is offline", () => {
    const html = renderToStaticMarkup(<BackupsPage />);

    expect(html).toContain("bigrag-worker is offline");
    expect(html).toContain("Worker offline");
    expect(html).toMatch(/disabled=""/);
  });
});
