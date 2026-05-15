import { PageHeader } from "@/components/ui/page-header";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";

export const VectorStoragePage = () => (
  <div className="flex flex-col gap-5">
    <PageHeader
      className="mb-0"
      description="Choose the instance-level vector backend, keep provider credentials current, and validate the active search index target."
      title="Vector Storage"
    />
    <InstanceSettingsTab group="vector_store" />
  </div>
);
