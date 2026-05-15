import { CheckCircle2, Database, Search } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";

export const VectorStoragePage = () => (
  <div className="flex flex-col gap-5">
    <PageHeader
      className="mb-0"
      description="Choose the instance-level vector backend, keep provider credentials current, and validate the active search index target."
      title="Vector Storage"
    />
    <VectorStorageGuide />
    <InstanceSettingsTab group="vector_store" />
  </div>
);

const VectorStorageGuide = () => (
  <section className="rounded-md border border-border bg-card p-4">
    <div className="min-w-0">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Retrieval storage
      </div>
      <h2 className="mt-1 text-base font-semibold">Select, validate, reindex when needed</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
        Vector storage is an infrastructure decision, so keep it separate from general settings.
        Provider switches validate before saving, but existing vectors still need re-ingestion when
        moving between backends.
      </p>
    </div>
    <div className="mt-4 grid gap-3 md:grid-cols-3">
      <VectorStorageStep
        icon={<Database className="size-4" />}
        label="Backend"
        value="Qdrant or turbopuffer"
      />
      <VectorStorageStep
        icon={<CheckCircle2 className="size-4" />}
        label="Validation"
        value="Checked on save"
      />
      <VectorStorageStep
        icon={<Search className="size-4" />}
        label="Search modes"
        value="Hybrid stays Qdrant-only"
      />
    </div>
  </section>
);

const VectorStorageStep = ({
  icon,
  label,
  value,
}: {
  readonly icon: React.ReactNode;
  readonly label: string;
  readonly value: string;
}) => (
  <div className="rounded-md border border-border bg-background p-3">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {icon}
      {label}
    </div>
    <div className="mt-2 text-sm font-semibold">{value}</div>
  </div>
);
