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

describe("BackupsPage", () => {
  it("does not render the realtime transport badge in the page header", () => {
    const html = renderToStaticMarkup(<BackupsPage />);

    expect(html).toContain("Backups");
    expect(html).toContain("Readable backups");
    expect(html).not.toContain(">live<");
    expect(html).not.toContain(">polling<");
  });
});
