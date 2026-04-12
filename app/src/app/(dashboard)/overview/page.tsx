"use client";

import {
  ArrowUpRight,
  BookOpen,
  Clock,
  FileText,
  HardDrive,
  KeyRound,
  Layers,
  ShieldCheck,
  Sparkles,
  Webhook,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { useSession } from "@/hooks/use-auth";
import { useCollections } from "@/hooks/use-collections";
import { usePlatformStats, useReadiness } from "@/hooks/use-platform";
import { cn } from "@/lib/cn";
import { formatBytes, formatNumber, formatRelative } from "@/lib/format";

const OverviewPage = () => {
  const { data: session } = useSession();
  const { data: stats, isPending: statsPending } = usePlatformStats();
  const { data: readiness } = useReadiness();
  const { data: collections } = useCollections();

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 5) return "Burning the midnight oil,";
    if (h < 12) return "Good morning,";
    if (h < 18) return "Good afternoon,";
    return "Good evening,";
  })();

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Overview"
        title={`${greeting} ${session?.user.display_name?.split(" ")[0] || session?.user.email}`}
        description="A snapshot of your collections, ingestion queue, and system health."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={BookOpen}
          label="Collections"
          value={statsPending ? undefined : formatNumber(stats?.collections ?? 0)}
        />
        <StatCard
          icon={FileText}
          label="Documents"
          value={statsPending ? undefined : formatNumber(stats?.documents.total ?? 0)}
          sub={
            stats
              ? `${formatNumber(stats.documents.ready)} ready · ${formatNumber(stats.documents.processing + stats.documents.pending)} in queue`
              : undefined
          }
        />
        <StatCard
          icon={Layers}
          label="Chunks"
          value={statsPending ? undefined : formatNumber(stats?.documents.total_chunks ?? 0)}
          sub={stats ? `${formatNumber(stats.documents.total_tokens)} tokens embedded` : undefined}
        />
        <StatCard
          icon={HardDrive}
          label="Storage"
          value={statsPending ? undefined : formatBytes(stats?.documents.total_size_bytes ?? 0)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent collections</CardTitle>
              <CardDescription>The last five collections you created or updated.</CardDescription>
            </div>
            <Link href="/collections" className="text-xs font-medium text-primary hover:underline">
              View all →
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {!collections ? (
              <div className="px-5 pb-6">
                <Spinner />
              </div>
            ) : collections.collections.length === 0 ? (
              <div className="px-5 pb-6 text-sm text-muted-foreground">
                No collections yet.{" "}
                <Link href="/collections" className="text-primary hover:underline">
                  Create your first →
                </Link>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {collections.collections.slice(0, 5).map((c) => (
                  <li key={c.id}>
                    <Link
                      href={`/collections/${encodeURIComponent(c.name)}`}
                      className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-muted"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">{c.name}</span>
                          <Badge variant="primary">{c.embedding_model}</Badge>
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                          {c.description || "No description"}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{formatNumber(c.document_count)} docs</span>
                        <span className="hidden sm:inline">{formatRelative(c.updated_at)}</span>
                        <ArrowUpRight className="h-4 w-4" />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System health</CardTitle>
            <CardDescription>Readiness of connected services.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <HealthRow label="Postgres" ok={readiness?.postgres} />
            <HealthRow label="Milvus" ok={readiness?.milvus} />
            <HealthRow label="Redis" ok={readiness?.redis} />
            <HealthRow
              label="Embeddings"
              ok={readiness?.embedding}
              detail={readiness?.embedding_error}
            />
            {readiness?.version && (
              <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" /> {readiness.status}
                </span>
                <span>v{readiness.version}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <QuickLink
          icon={Sparkles}
          title="Run a query"
          description="Test retrieval across any collection"
          href="/playground"
        />
        <QuickLink
          icon={KeyRound}
          title="Mint an API key"
          description="Issue keys for external clients"
          href="/api-keys"
        />
        <QuickLink
          icon={Webhook}
          title="Wire up webhooks"
          description="Get notified when docs are ready"
          href="/webhooks"
        />
      </div>
    </div>
  );
};

const StatCard = ({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: typeof BookOpen;
  label: string;
  value: string | undefined;
  sub?: string;
}) => (
  <Card>
    <CardContent className="pt-5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">
        {value ?? <Spinner size="sm" />}
      </div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </CardContent>
  </Card>
);

const HealthRow = ({
  label,
  ok,
  detail,
}: {
  label: string;
  ok: boolean | undefined;
  detail?: string;
}) => (
  <div className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm">
    <div className="flex items-center gap-2">
      <ShieldCheck
        className={cn(
          "h-4 w-4",
          ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
        )}
      />
      <span>{label}</span>
    </div>
    <div
      className={cn(
        "text-xs font-medium",
        ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
      )}
      title={detail}
    >
      {ok === undefined ? "—" : ok ? "operational" : "degraded"}
    </div>
  </div>
);

const QuickLink = ({
  icon: Icon,
  title,
  description,
  href,
}: {
  icon: typeof BookOpen;
  title: string;
  description: string;
  href: string;
}) => (
  <Link
    href={href}
    className="group rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary hover:bg-accent"
  >
    <div className="flex items-start gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-foreground group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1 font-medium text-sm">
          {title}
          <ArrowUpRight className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
    </div>
  </Link>
);

export default OverviewPage;
