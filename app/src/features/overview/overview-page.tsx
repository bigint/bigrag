import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import { ArrowUpRight, BookOpen, MessageCircle } from "lucide-react";
import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Page } from "@/components/ui/page";
import { Panel } from "@/components/ui/panel";
import { Spinner } from "@/components/ui/spinner";
import { AccessCommandCenter } from "@/features/overview/access-command-center";
import { DocumentReadinessPanel } from "@/features/overview/document-readiness-panel";
import { IngestionQueuePanel } from "@/features/overview/ingestion-queue-panel";
import { MetricCards } from "@/features/overview/metric-cards";
import { QuickActions } from "@/features/overview/quick-actions";
import { type HealthService, SystemHealthPanel } from "@/features/overview/system-health-panel";
import { useOverviewAutoRefresh } from "@/features/overview/use-overview-auto-refresh";
import { getWorkerAvailability } from "@/features/workers/worker-status";
import { useAccessOverview } from "@/hooks/use-access-logs";
import { useSession } from "@/hooks/use-auth";
import { useCollections } from "@/hooks/use-collections";
import { usePlatformStats, useReadiness } from "@/hooks/use-platform";
import { cn } from "@/lib/cn";
import { formatNumber, formatRelative } from "@/lib/format";

export const OverviewPage = () => {
  const { data: session } = useSession();
  const { data: stats, isPending: statsPending } = usePlatformStats();
  const { data: readiness } = useReadiness();
  const { data: collectionsData } = useCollections();
  const canSeeAccess = session?.user.role === "admin";
  const { data: accessOverview, isPending: accessPending } = useAccessOverview(canSeeAccess);

  const collections = collectionsData?.collections ?? [];
  const firstName = session?.user.display_name?.split(" ")[0] || session?.user.email || "there";
  const docs = stats?.documents;
  const queuedDocs = (docs?.pending ?? 0) + (docs?.processing ?? 0);
  const readyPct = docs?.total ? Math.round((docs.ready / docs.total) * 100) : 0;
  const failedPct = docs?.total ? Math.round((docs.failed / docs.total) * 100) : 0;
  const workerAvailability = getWorkerAvailability(stats);
  const queueHealth = stats?.queue_health;
  const services = useMemo<HealthService[]>(
    () => [
      { label: "Postgres", ok: readiness?.postgres },
      { label: "Vector store", ok: readiness?.vector_store },
      { label: "Redis", ok: readiness?.redis },
      { detail: readiness?.embedding_error, label: "Embeddings", ok: readiness?.embedding },
      {
        detail: workerAvailability.message,
        label: "Worker",
        ok: workerAvailability.unknown ? undefined : workerAvailability.online,
      },
    ],
    [readiness, workerAvailability],
  );
  const servicesOnline = services.filter((service) => service.ok).length;
  const queueItems = useMemo(
    () => Object.entries(stats?.queue ?? {}).filter(([, value]) => value > 0),
    [stats?.queue],
  );

  useOverviewAutoRefresh(stats, collectionsData);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background px-4 py-6 md:px-8 lg:px-10">
      <Page.Container className="flex w-full flex-col gap-6">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold leading-tight tracking-normal">
              Good to see you, {firstName}
            </h1>
            <p className="mt-2 max-w-4xl text-pretty text-sm leading-6 text-muted-foreground">
              Live readout of retrieval coverage, ingestion health, and the systems behind bigRAG.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PillLink to="/chat" icon={MessageCircle} label="Ask bigRAG" />
            <PillLink to="/collections" icon={BookOpen} label="New collection" primary />
          </div>
        </header>

        <MetricCards
          statsPending={statsPending}
          collectionsTotal={stats?.collections ?? 0}
          visibleCollections={collections.length}
          docsTotal={docs?.total ?? 0}
          docsReady={docs?.ready ?? 0}
          queuedDocs={queuedDocs}
          totalChunks={docs?.total_chunks ?? 0}
          totalTokens={docs?.total_tokens ?? 0}
          totalSizeBytes={docs?.total_size_bytes ?? 0}
          servicesOnline={servicesOnline}
          servicesTotal={services.length}
        />

        {canSeeAccess && <AccessCommandCenter overview={accessOverview} pending={accessPending} />}

        <section className="grid gap-4 xl:grid-cols-3">
          <DocumentReadinessPanel
            ready={docs?.ready ?? 0}
            processing={docs?.processing ?? 0}
            pending={docs?.pending ?? 0}
            failed={docs?.failed ?? 0}
            total={docs?.total ?? 0}
            readyPct={readyPct}
            failedPct={failedPct}
          />

          <SystemHealthPanel services={services} status={readiness?.status} />
        </section>

        <section className="grid gap-4 xl:grid-cols-5">
          <Panel className="p-0 xl:col-span-3">
            <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
              <div>
                <h2 className="text-base font-semibold">Recent collections</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Last updated knowledge bases and their retrieval defaults.
                </p>
              </div>
              <Link
                to="/collections"
                className="shrink-0 text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                View all
              </Link>
            </div>
            {collectionsData ? (
              collections.length === 0 ? (
                <div className="px-5 py-6 text-sm text-muted-foreground">
                  No collections yet. Create one to start tracking coverage.
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {collections.slice(0, 6).map((collection) => (
                    <li key={collection.id}>
                      <Link
                        params={{ name: collection.name }}
                        to="/collections/$name"
                        className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-muted"
                      >
                        <div className="min-w-0">
                          <div className="flex min-w-0 items-center gap-2">
                            <span className="truncate text-sm font-semibold">
                              {collection.name}
                            </span>
                            <Badge variant="primary">{collection.default_search_mode}</Badge>
                          </div>
                          <div className="mt-1 truncate text-xs text-muted-foreground">
                            {collection.description || collection.embedding_model}
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-4 text-xs text-muted-foreground">
                          <span className="tabular-nums">
                            {formatNumber(collection.document_count)} docs
                          </span>
                          <span className="hidden w-24 text-right sm:inline">
                            {formatRelative(collection.updated_at)}
                          </span>
                          <ArrowUpRight className="size-4" />
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )
            ) : (
              <div className="px-5 py-6">
                <Spinner />
              </div>
            )}
          </Panel>

          <div className="grid gap-4 xl:col-span-2">
            <IngestionQueuePanel
              queueItems={queueItems}
              queueStatus={queueHealth?.status}
              queueReasons={queueHealth?.reasons}
              workerAvailability={workerAvailability}
            />
            <QuickActions />
          </div>
        </section>
      </Page.Container>
    </div>
  );
};

const PillLink = ({
  icon: Icon,
  label,
  primary,
  to,
}: {
  icon: LucideIcon;
  label: string;
  primary?: boolean;
  to: "/" | "/chat" | "/collections";
}) => (
  <Link
    to={to}
    className={cn(
      "inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-xs font-semibold",
      primary
        ? "border-primary bg-primary text-primary-foreground"
        : "border-border bg-background text-foreground hover:bg-muted",
    )}
  >
    <Icon className="size-3.5" />
    {label}
  </Link>
);
