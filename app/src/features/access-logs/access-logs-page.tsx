import { RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PageShell } from "@/components/ui/page-shell";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useAccessLogs, useAccessOverview } from "@/hooks/use-access-logs";
import { useSession } from "@/hooks/use-auth";
import { cn } from "@/lib/cn";
import { formatNumber, formatRelative } from "@/lib/format";
import type { AccessLogEntry } from "@/types/bigrag";

export const AccessLogsPage = () => {
  const { data: session } = useSession();
  const canSeeAccess = session?.user.role === "admin";
  const [pathFilter, setPathFilter] = useState("");
  const [actorId, setActorId] = useState("");
  const [statusFamily, setStatusFamily] = useState("");
  const [sort, setSort] = useState<"newest" | "latency">("newest");
  const [selected, setSelected] = useState<AccessLogEntry | null>(null);
  const overview = useAccessOverview(canSeeAccess, 7);
  const logs = useAccessLogs(
    {
      actor_id: actorId,
      limit: 100,
      path: pathFilter,
      status_family: statusFamily as "2xx" | "3xx" | "4xx" | "5xx" | undefined,
    },
    canSeeAccess,
  );
  const refresh = () => {
    void logs.refetch();
    void overview.refetch();
  };
  const entries = [...(logs.data?.entries ?? [])].sort((a, b) =>
    sort === "latency" ? b.latency_ms - a.latency_ms : 0,
  );

  if (session && !canSeeAccess) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center bg-background px-6">
        <div className="max-w-md text-center">
          <ShieldCheck className="mx-auto size-8 text-muted-foreground" />
          <h1 className="mt-4 text-xl font-semibold">Admin access required</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Access logs include actor, IP, endpoint, and request outcome.
          </p>
        </div>
      </div>
    );
  }

  return (
    <PageShell>
      <PageHeader
        actions={
          <Button disabled={logs.isFetching} onClick={refresh} size="sm" variant="outline">
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        }
        className="mb-0"
        description="Trace query, vector, and evaluation traffic by actor, outcome, and latency."
        title="Access logs"
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Events" value={formatNumber(overview.data?.total_events ?? 0)} />
        <Stat
          label="Success rate"
          tone="success"
          value={`${(overview.data?.success_rate ?? 0).toFixed(1)}%`}
        />
        <Stat
          label="P95 latency"
          tone="warning"
          value={`${formatNumber(Math.round(overview.data?.p95_latency_ms ?? 0))} ms`}
        />
        <Stat label="Query events" value={formatNumber(overview.data?.query_events ?? 0)} />
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <div className="border-b border-border px-5 py-4">
          <div>
            <h2 className="text-base font-semibold">Access stream</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatNumber(logs.data?.total ?? 0)} events, newest first.
            </p>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_140px_140px_auto]">
            <Input
              aria-label="Path filter"
              onChange={(event) => setPathFilter(event.target.value)}
              placeholder="/v1/collections"
              value={pathFilter}
            />
            <Input
              aria-label="Actor id filter"
              onChange={(event) => setActorId(event.target.value)}
              placeholder="Actor id"
              value={actorId}
            />
            <Select
              aria-label="Status family"
              onChange={(value) => setStatusFamily(value === "all" ? "" : value)}
              options={[
                { value: "all", label: "All status" },
                { value: "2xx", label: "2xx" },
                { value: "3xx", label: "3xx" },
                { value: "4xx", label: "4xx" },
                { value: "5xx", label: "5xx" },
              ]}
              value={statusFamily || "all"}
            />
            <Select
              aria-label="Sort"
              onChange={(value) => setSort(value as "newest" | "latency")}
              options={[
                { value: "newest", label: "Newest" },
                { value: "latency", label: "Latency" },
              ]}
              value={sort}
            />
            <Button
              variant="secondary"
              onClick={() => {
                setPathFilter("");
                setActorId("");
                setStatusFamily("");
              }}
            >
              Clear
            </Button>
          </div>
        </div>

        {logs.isPending ? (
          <div className="px-5 py-10">
            <Spinner />
          </div>
        ) : logs.isError ? (
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-10">
            <p className="text-sm text-destructive">
              {logs.error instanceof Error ? logs.error.message : "Access logs failed"}
            </p>
            <Button onClick={() => logs.refetch()} variant="secondary">
              Retry
            </Button>
          </div>
        ) : (logs.data?.entries.length ?? 0) === 0 ? (
          <div className="px-5 py-10 text-sm text-muted-foreground">
            No access events match this view.
          </div>
        ) : (
          <AccessLogTable entries={entries} onSelect={setSelected} />
        )}
      </section>
      {selected && (
        <section className="rounded-xl border border-border bg-background p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">Access detail</h2>
            <Button onClick={() => setSelected(null)} size="sm" variant="secondary">
              Close
            </Button>
          </div>
          <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <Detail label="Actor" value={selected.api_key_name ?? selected.actor_email ?? "-"} />
            <Detail label="Path" value={`${selected.method} ${selected.path}`} />
            <Detail label="Status" value={String(selected.status_code)} />
            <Detail label="Latency" value={`${Math.round(selected.latency_ms)} ms`} />
          </div>
        </section>
      )}
    </PageShell>
  );
};

const Stat = ({
  label,
  tone,
  value,
}: {
  label: string;
  tone?: "success" | "warning";
  value: string;
}) => (
  <div className="rounded-xl border border-border bg-background p-4">
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
    </div>
    <div
      className={cn(
        "mt-3 text-2xl font-semibold tabular-nums",
        tone === "success" && "text-success",
        tone === "warning" && "text-warning",
      )}
    >
      {value}
    </div>
  </div>
);

const AccessLogTable = ({
  entries,
  onSelect,
}: {
  entries: AccessLogEntry[];
  onSelect: (entry: AccessLogEntry) => void;
}) => (
  <div className="divide-y divide-border">
    {entries.map((entry) => (
      <button
        type="button"
        className="grid w-full gap-4 px-5 py-4 text-left hover:bg-muted/60 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_12rem_9rem]"
        key={entry.id}
        onClick={() => onSelect(entry)}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge entry={entry} />
            <span className="truncate text-sm font-semibold">{entry.action}</span>
          </div>
          <div className="mt-1 flex min-w-0 text-xs text-muted-foreground">
            <span className="truncate">{entry.collection_name ?? entry.resource_type}</span>
          </div>
        </div>

        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{entry.path}</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <MetaPill>{entry.method}</MetaPill>
            <MetaPill>{entry.auth_method ?? "anonymous"}</MetaPill>
          </div>
        </div>

        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">
            {entry.api_key_name ?? entry.actor_email ?? "anonymous"}
          </div>
          <div className="mt-1 truncate text-xs text-muted-foreground">{entry.ip ?? "no ip"}</div>
        </div>

        <div className="flex items-center justify-start gap-4 xl:justify-end">
          <div className="text-right">
            <div className="text-sm font-semibold tabular-nums">
              {formatNumber(Math.round(entry.latency_ms))} ms
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {formatRelative(entry.created_at)}
            </div>
          </div>
        </div>
      </button>
    ))}
  </div>
);

const Detail = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-md border border-border bg-muted/30 p-3">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className="mt-1 break-all font-mono text-xs">{value}</div>
  </div>
);

const StatusBadge = ({ entry }: { entry: AccessLogEntry }) => (
  <Badge variant={entry.success ? "success" : "error"}>{entry.status_code}</Badge>
);

const MetaPill = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex h-6 max-w-full items-center rounded-full bg-muted px-2 text-xs font-semibold text-muted-foreground">
    <span className="truncate">{children}</span>
  </span>
);
