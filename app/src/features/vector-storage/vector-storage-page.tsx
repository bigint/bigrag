import { Cloud, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { PageShell } from "@/components/ui/page-shell";
import { Spinner } from "@/components/ui/spinner";
import { Tabs } from "@/components/ui/tabs";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { useVectorStorageOverview } from "@/hooks/use-vector-storage";
import { formatBytes, formatNumber } from "@/lib/format";

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
    description: "Qdrant connection, startup behavior, and HNSW search tuning.",
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
  const overview = useVectorStorageOverview();

  return (
    <PageShell>
      <PageHeader
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
      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {overview.isPending ? (
            <Spinner />
          ) : overview.isError ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-destructive">
                {overview.error instanceof Error
                  ? overview.error.message
                  : "Vector storage overview failed"}
              </p>
              <Button onClick={() => overview.refetch()} variant="secondary">
                Retry
              </Button>
            </div>
          ) : overview.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Collections" value={formatNumber(overview.data.totals.collections)} />
                <Metric label="Documents" value={formatNumber(overview.data.totals.documents)} />
                <Metric label="Chunks" value={formatNumber(overview.data.totals.chunks)} />
                <Metric label="Stored files" value={formatBytes(overview.data.totals.bytes)} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {Object.entries(overview.data.provider_health).map(([name, health]) => (
                  <div key={name} className="rounded-md border border-border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-semibold capitalize">{name}</span>
                      <Badge
                        variant={
                          health.status === "ok"
                            ? "success"
                            : health.configured
                              ? "error"
                              : "neutral"
                        }
                      >
                        {health.status.replace("_", " ")}
                      </Badge>
                    </div>
                    {health.error && (
                      <p className="mt-2 text-xs text-destructive">{health.error}</p>
                    )}
                  </div>
                ))}
              </div>
              <div className="overflow-hidden rounded-md border border-border">
                {overview.data.collections.map((collection) => (
                  <div
                    key={collection.name}
                    className="grid grid-cols-[1fr_auto_auto_auto] gap-3 border-b border-border px-3 py-2 text-sm last:border-b-0"
                  >
                    <span className="font-medium">{collection.name}</span>
                    <Badge variant="neutral">{collection.provider}</Badge>
                    <span className="text-muted-foreground">
                      {formatNumber(collection.documents)} docs
                    </span>
                    <span className="text-muted-foreground">
                      {formatNumber(collection.chunks)} chunks
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
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
    </PageShell>
  );
};

const Metric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-md border border-border bg-muted/30 p-3">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className="mt-1 text-lg font-semibold">{value}</div>
  </div>
);
