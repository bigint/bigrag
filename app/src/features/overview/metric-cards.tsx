import type { LucideIcon } from "lucide-react";
import { BookOpen, FileText, HardDrive, Hash, Layers } from "lucide-react";
import { Panel } from "@/components/ui/panel";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes, formatNumber } from "@/lib/format";

interface MetricCardsProps {
  readonly statsPending: boolean;
  readonly collectionsTotal: number;
  readonly visibleCollections: number;
  readonly docsTotal: number;
  readonly docsReady: number;
  readonly queuedDocs: number;
  readonly totalChunks: number;
  readonly totalTokens: number;
  readonly totalSizeBytes: number;
  readonly servicesOnline: number;
  readonly servicesTotal: number;
}

export const MetricCards = ({
  statsPending,
  collectionsTotal,
  visibleCollections,
  docsTotal,
  docsReady,
  queuedDocs,
  totalChunks,
  totalTokens,
  totalSizeBytes,
  servicesOnline,
  servicesTotal,
}: MetricCardsProps) => (
  <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
    <MetricCard
      icon={BookOpen}
      label="Collections"
      value={statsPending ? undefined : formatNumber(collectionsTotal)}
      sub={`${formatNumber(visibleCollections)} visible in the admin UI`}
    />
    <MetricCard
      icon={FileText}
      label="Documents"
      value={statsPending ? undefined : formatNumber(docsTotal)}
      sub={`${formatNumber(docsReady)} ready, ${formatNumber(queuedDocs)} queued`}
    />
    <MetricCard
      icon={Layers}
      label="Chunks"
      value={statsPending ? undefined : formatNumber(totalChunks)}
      sub="Indexed vector chunks"
    />
    <MetricCard
      icon={Hash}
      label="Tokens stored"
      value={statsPending ? undefined : formatNumber(totalTokens)}
      sub="Across indexed documents"
    />
    <MetricCard
      icon={HardDrive}
      label="Storage"
      value={statsPending ? undefined : formatBytes(totalSizeBytes)}
      sub={`${servicesOnline}/${servicesTotal} services online`}
    />
  </section>
);

const MetricCard = ({
  icon: Icon,
  label,
  sub,
  value,
}: {
  icon: LucideIcon;
  label: string;
  sub?: string;
  value: string | undefined;
}) => (
  <Panel className="p-4">
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      <Icon className="size-4 text-muted-foreground" />
    </div>
    <div className="mt-3 min-h-8 text-2xl font-semibold tabular-nums">
      {value ?? <Spinner size="sm" />}
    </div>
    {sub && <div className="mt-1 truncate text-xs text-muted-foreground">{sub}</div>}
  </Panel>
);
