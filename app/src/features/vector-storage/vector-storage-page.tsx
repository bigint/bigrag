import { Cloud, Database } from "lucide-react";
import { Page } from "@/components/ui/page";
import { Tabs } from "@/components/ui/tabs";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { VectorMigrationPanel } from "@/features/vector-storage/vector-migration-panel";

export type VectorStorageProvider = "qdrant" | "turbopuffer";

type VectorStoragePageProps = {
  readonly provider?: string;
  readonly onProviderChange?: (provider: VectorStorageProvider) => void;
};

const VECTOR_STORAGE_TABS = [
  { icon: Database, label: "Qdrant", value: "qdrant" },
  { icon: Cloud, label: "turbopuffer", value: "turbopuffer" },
];

const VECTOR_PROVIDER_SETTINGS: Record<
  VectorStorageProvider,
  {
    readonly description: string;
    readonly emptyState: string;
    readonly eyebrow: string;
    readonly keys: readonly string[];
    readonly recommendedAction: string;
    readonly title: string;
  }
> = {
  qdrant: {
    description: "Qdrant connection, readiness policy, and HNSW search tuning.",
    emptyState: "Qdrant settings are not available from this API.",
    eyebrow: "Self-hosted index",
    keys: ["qdrant_url", "qdrant_connect_timeout_seconds", "qdrant_required", "qdrant_search_ef"],
    recommendedAction: "Save Qdrant when the URL and readiness policy match this deployment.",
    title: "Qdrant",
  },
  turbopuffer: {
    description: "turbopuffer credentials, region, and namespace routing.",
    emptyState: "turbopuffer settings are not available from this API.",
    eyebrow: "Managed index",
    keys: ["turbopuffer_api_key", "turbopuffer_region", "turbopuffer_namespace_prefix"],
    recommendedAction: "Save turbopuffer after the API key, region, and namespace prefix are set.",
    title: "turbopuffer",
  },
};

const getVectorStorageProvider = (value: unknown): VectorStorageProvider | undefined =>
  value === "qdrant" || value === "turbopuffer" ? value : undefined;

export const VectorStoragePage = ({ provider, onProviderChange }: VectorStoragePageProps) => {
  const activeProvider = getVectorStorageProvider(provider) ?? "qdrant";
  const settings = VECTOR_PROVIDER_SETTINGS[activeProvider];

  return (
    <Page.Shell>
      <Page.Header
        className="mb-0"
        description="Keep vector backend credentials current. Collections choose Qdrant or turbopuffer when they are created."
        title="Vector Storage"
      />
      <Tabs
        onChange={(value) => {
          const nextProvider = getVectorStorageProvider(value);
          if (nextProvider) onProviderChange?.(nextProvider);
        }}
        tabs={VECTOR_STORAGE_TABS}
        value={activeProvider}
      />
      <InstanceSettingsTab
        group="vector_store"
        includeKeys={settings.keys}
        layoutOverride={{
          description: settings.description,
          emptyState: settings.emptyState,
          eyebrow: settings.eyebrow,
          recommendedAction: settings.recommendedAction,
          title: settings.title,
        }}
      />
      <VectorMigrationPanel />
    </Page.Shell>
  );
};
