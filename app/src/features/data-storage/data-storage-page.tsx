import { Page } from "@/components/ui/page";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";

export const DataStoragePage = () => (
  <Page.Shell>
    <Page.Header
      className="mb-0"
      description="Configure where uploaded source files are stored, from local development paths to S3-compatible production buckets."
      title="Data Storage"
    />
    <InstanceSettingsTab group="storage" />
  </Page.Shell>
);
