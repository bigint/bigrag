"use client";

import type { LucideIcon } from "lucide-react";
import {
  ArrowUpRight,
  BookOpen,
  Database,
  FileText,
  HardDrive,
  KeyRound,
  Layers,
  MessageCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { useSession } from "@/hooks/use-auth";
import { useCollections } from "@/hooks/use-collections";
import { usePlatformStats, useReadiness } from "@/hooks/use-platform";
import { cn } from "@/lib/cn";
import { formatBytes, formatNumber, formatRelative } from "@/lib/format";

const QUICK_ACTIONS = [
  {
    description: "Test retrieval with citations",
    href: "/playground",
    icon: MessageCircle,
    title: "Run a query",
  },
  {
    description: "Add documents or S3 sources",
    href: "/collections",
    icon: BookOpen,
    title: "Manage collections",
  },
  {
    description: "Create scoped client access",
    href: "/api-keys",
    icon: KeyRound,
    title: "Mint API key",
  },
] as const;

const OverviewPage = () => {
  const { data: session } = useSession();
  const { data: stats, isPending: statsPending } = usePlatformStats();
  const { data: readiness } = useReadiness();
  const { data: collectionsData } = useCollections();

  const collections = collectionsData?.collections ?? [];
  const firstName = session?.user.display_name?.split(" ")[0] || session?.user.email || "there";
  const docs = stats?.documents;
  const queuedDocs = (docs?.pending ?? 0) + (docs?.processing ?? 0);
  const readyPct = docs?.total ? Math.round((docs.ready / docs.total) * 100) : 0;
  const failedPct = docs?.total ? Math.round((docs.failed / docs.total) * 100) : 0;
  const services = [
    { label: "Postgres", ok: readiness?.postgres },
    { label: "Qdrant", ok: readiness?.qdrant },
    { label: "Redis", ok: readiness?.redis },
    { detail: readiness?.embedding_error, label: "Embeddings", ok: readiness?.embedding },
  ];
  const servicesOnline = services.filter((service) => service.ok).length;
  const queueItems = Object.entries(stats?.queue ?? {}).filter(([, value]) => value > 0);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background px-4 py-6 md:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold text-muted-foreground">Overview</p>
            <h1 className="mt-1 text-3xl font-semibold leading-tight tracking-normal">
              Good to see you, {firstName}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Live readout of retrieval coverage, ingestion health, and the systems behind bigRAG.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PillLink href="/playground" icon={Sparkles} label="Ask bigRAG" />
            <PillLink href="/collections" icon={BookOpen} label="New collection" primary />
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            icon={BookOpen}
            label="Collections"
            value={statsPending ? undefined : formatNumber(stats?.collections ?? 0)}
            sub={`${formatNumber(collections.length)} visible in Studio`}
          />
          <MetricCard
            icon={FileText}
            label="Documents"
            value={statsPending ? undefined : formatNumber(docs?.total ?? 0)}
            sub={`${formatNumber(docs?.ready ?? 0)} ready, ${formatNumber(queuedDocs)} queued`}
          />
          <MetricCard
            icon={Layers}
            label="Chunks"
            value={statsPending ? undefined : formatNumber(docs?.total_chunks ?? 0)}
            sub={`${formatNumber(docs?.total_tokens ?? 0)} tokens embedded`}
          />
          <MetricCard
            icon={HardDrive}
            label="Storage"
            value={statsPending ? undefined : formatBytes(docs?.total_size_bytes ?? 0)}
            sub={`${servicesOnline}/4 services online`}
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <Panel className="xl:col-span-2">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Document readiness</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Current processing state across all collections.
                </p>
              </div>
              <Badge variant={failedPct > 0 ? "warning" : "success"}>{readyPct}% ready</Badge>
            </div>

            <div className="mt-5">
              <StatusBar
                failed={docs?.failed ?? 0}
                pending={docs?.pending ?? 0}
                processing={docs?.processing ?? 0}
                ready={docs?.ready ?? 0}
                total={docs?.total ?? 0}
              />
              <div className="mt-4 grid gap-2 sm:grid-cols-4">
                <StatusCount label="Ready" value={docs?.ready} tone="success" />
                <StatusCount label="Processing" value={docs?.processing} tone="info" />
                <StatusCount label="Pending" value={docs?.pending} tone="warning" />
                <StatusCount label="Failed" value={docs?.failed} tone="error" />
              </div>
            </div>
          </Panel>

          <Panel>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">System health</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Readiness of storage, vector search, cache, and embedding calls.
                </p>
              </div>
              <Badge variant={readiness?.status === "ok" ? "success" : "warning"} dot>
                {readiness?.status ?? "checking"}
              </Badge>
            </div>
            <div className="mt-4 space-y-2">
              {services.map((service) => (
                <HealthRow
                  detail={service.detail}
                  key={service.label}
                  label={service.label}
                  ok={service.ok}
                />
              ))}
            </div>
          </Panel>
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
                href="/collections"
                className="shrink-0 text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground"
              >
                View all
              </Link>
            </div>
            {!collectionsData ? (
              <div className="px-5 py-6">
                <Spinner />
              </div>
            ) : collections.length === 0 ? (
              <div className="px-5 py-6 text-sm text-muted-foreground">
                No collections yet. Create one to start tracking coverage.
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {collections.slice(0, 6).map((collection) => (
                  <li key={collection.id}>
                    <Link
                      href={`/collections/${encodeURIComponent(collection.name)}`}
                      className="flex items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-muted"
                    >
                      <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="truncate text-sm font-semibold">{collection.name}</span>
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
            )}
          </Panel>

          <div className="grid gap-4 xl:col-span-2">
            <Panel>
              <h2 className="text-base font-semibold">Ingestion queue</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Work waiting behind document upload, S3 sync, and reprocessing.
              </p>
              <div className="mt-4 space-y-2">
                {queueItems.length === 0 ? (
                  <div className="rounded-2xl border border-border bg-muted px-3 py-3 text-sm font-semibold">
                    Queue is clear
                  </div>
                ) : (
                  queueItems.map(([label, value]) => (
                    <QueueRow key={label} label={label} value={value} />
                  ))
                )}
              </div>
            </Panel>

            <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
              {QUICK_ACTIONS.map((action) => (
                <QuickAction key={action.href} {...action} />
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

const Panel = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn("rounded-3xl border border-border bg-background p-5", className)}>
    {children}
  </div>
);

const PillLink = ({
  href,
  icon: Icon,
  label,
  primary,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  primary?: boolean;
}) => (
  <Link
    href={href}
    className={cn(
      "inline-flex h-9 items-center justify-center gap-2 rounded-full border px-3 text-xs font-semibold transition-all active:scale-95",
      primary
        ? "border-primary bg-primary text-primary-foreground"
        : "border-border bg-background text-foreground hover:bg-muted",
    )}
  >
    <Icon className="size-3.5" />
    {label}
  </Link>
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

const StatusBar = ({
  failed,
  pending,
  processing,
  ready,
  total,
}: {
  failed: number;
  pending: number;
  processing: number;
  ready: number;
  total: number;
}) => {
  const segments = [
    { className: "bg-success", label: "Ready", value: ready },
    { className: "bg-info", label: "Processing", value: processing },
    { className: "bg-warning", label: "Pending", value: pending },
    { className: "bg-destructive", label: "Failed", value: failed },
  ].filter((segment) => segment.value > 0);

  if (total <= 0) {
    return <div className="h-3 rounded-full bg-muted" />;
  }

  return (
    <div
      aria-label="Document status distribution"
      className="flex h-3 overflow-hidden rounded-full bg-muted"
      role="img"
    >
      {segments.map((segment) => (
        <div
          aria-hidden="true"
          className={segment.className}
          key={segment.label}
          style={{ width: `${Math.max(2, (segment.value / total) * 100)}%` }}
        />
      ))}
    </div>
  );
};

const StatusCount = ({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "error" | "info" | "success" | "warning";
  value: number | undefined;
}) => (
  <div className="rounded-2xl border border-border bg-muted/60 px-3 py-2">
    <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
      <span
        className={cn(
          "size-1.5 rounded-full",
          tone === "success" && "bg-success",
          tone === "info" && "bg-info",
          tone === "warning" && "bg-warning",
          tone === "error" && "bg-destructive",
        )}
      />
      {label}
    </div>
    <div className="mt-1 text-lg font-semibold tabular-nums">{formatNumber(value ?? 0)}</div>
  </div>
);

const HealthRow = ({
  detail,
  label,
  ok,
}: {
  detail?: string;
  label: string;
  ok: boolean | undefined;
}) => (
  <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted/60 px-3 py-2.5">
    <div className="flex min-w-0 items-center gap-2">
      <ShieldCheck
        className={cn(
          "size-4 shrink-0",
          ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
        )}
      />
      <span className="truncate text-sm font-semibold">{label}</span>
    </div>
    <span
      className={cn(
        "shrink-0 text-xs font-semibold",
        ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
      )}
      title={detail}
    >
      {ok === undefined ? "checking" : ok ? "online" : "degraded"}
    </span>
  </div>
);

const QueueRow = ({ label, value }: { label: string; value: number }) => (
  <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted/60 px-3 py-2.5">
    <div className="flex items-center gap-2">
      <Database className="size-4 text-muted-foreground" />
      <span className="text-sm font-semibold capitalize">{label.replaceAll("_", " ")}</span>
    </div>
    <span className="text-sm font-semibold tabular-nums">{formatNumber(value)}</span>
  </div>
);

const QuickAction = ({
  description,
  href,
  icon: Icon,
  title,
}: {
  description: string;
  href: string;
  icon: LucideIcon;
  title: string;
}) => (
  <Link
    href={href}
    className="group flex items-center gap-3 rounded-3xl border border-border bg-background p-4 transition-all hover:border-neutral-200 active:scale-95"
  >
    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
      <Icon className="size-4" />
    </div>
    <div className="min-w-0 flex-1">
      <div className="text-sm font-semibold">{title}</div>
      <div className="truncate text-xs text-muted-foreground">{description}</div>
    </div>
    <ArrowUpRight className="size-4 text-muted-foreground" />
  </Link>
);

export default OverviewPage;
