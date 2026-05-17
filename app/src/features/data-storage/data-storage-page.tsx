import { PageHeader } from "@/components/ui/page-header";
import { PageShell } from "@/components/ui/page-shell";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";

export const DataStoragePage = () => (
  <PageShell>
    <PageHeader
      className="mb-0"
      description="Configure where uploaded source files are stored, from local development paths to S3-compatible production buckets."
      title="Data Storage"
    />
    <InstanceSettingsTab group="storage" />
  </PageShell>
);
