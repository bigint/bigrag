"use client";

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  Clock3,
  Database,
  KeyRound,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { TabButton } from "@/components/ui/tabs";
import { type AccessLogFilters, useAccessLogs, useAccessOverview } from "@/hooks/use-access-logs";
import { useSession } from "@/hooks/use-auth";
import { cn } from "@/lib/cn";
import { formatNumber, formatRelative } from "@/lib/format";
import type { AccessLogEntry, AccessLogOverview } from "@/types/bigrag";

type LogMode = "all" | "errors" | "queries" | "api-keys";

const FILTERS: Record<LogMode, { icon: LucideIcon; label: string; params: AccessLogFilters }> = {
  all: { icon: Activity, label: "All", params: { limit: 100 } },
  errors: { icon: AlertTriangle, label: "Errors", params: { limit: 100, success: false } },
  queries: { icon: Search, label: "Queries", params: { limit: 100, path: "query" } },
  "api-keys": { icon: KeyRound, label: "API keys", params: { auth_method: "api_key", limit: 100 } },
};

const AccessLogsPage = () => {
  const [mode, setMode] = useState<LogMode>("all");
  const { data: session } = useSession();
  const canSeeAccess = session?.user.role === "admin";
  const filters = useMemo(() => FILTERS[mode].params, [mode]);
  const overview = useAccessOverview(canSeeAccess, 7);
  const logs = useAccessLogs(filters, canSeeAccess);

  if (session && !canSeeAccess) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center bg-background px-6">
        <div className="max-w-md text-center">
          <ShieldCheck className="mx-auto size-8 text-muted-foreground" />
          <h1 className="mt-4 text-xl font-semibold">Admin access required</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Access logs include actor, IP, endpoint, and API-key telemetry.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background px-4 py-6 md:px-8 lg:px-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
        <section className="overflow-hidden rounded-3xl border border-border bg-primary text-primary-foreground">
          <div className="grid gap-0 lg:grid-cols-[1fr_21rem]">
            <div className="p-5 md:p-6">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-normal text-white/60">
                <Activity className="size-4" />
                RAG telemetry
              </div>
              <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h1 className="text-3xl font-semibold leading-tight tracking-normal md:text-4xl">
                    Access logs
                  </h1>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">
                    Endpoint-level visibility for sessions, API keys, query traffic, failures, and
                    latency across the RAG surface.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(FILTERS).map(([key, item]) => (
                    <TabButton
                      active={mode === key}
                      icon={item.icon}
                      key={key}
                      label={item.label}
                      onClick={() => setMode(key as LogMode)}
                      surface="inverse"
                    />
                  ))}
                </div>
              </div>
            </div>
            <div className="border-t border-white/10 p-5 lg:border-l lg:border-t-0">
              <AccessRadar overview={overview.data} pending={overview.isPending} />
            </div>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            icon={Activity}
            label="Events"
            value={formatNumber(overview.data?.total_events ?? 0)}
          />
          <Stat
            icon={ShieldCheck}
            label="Success rate"
            tone="success"
            value={`${(overview.data?.success_rate ?? 0).toFixed(1)}%`}
          />
          <Stat
            icon={Clock3}
            label="P95 latency"
            tone="warning"
            value={`${formatNumber(Math.round(overview.data?.p95_latency_ms ?? 0))} ms`}
          />
          <Stat
            icon={KeyRound}
            label="API key events"
            value={formatNumber(overview.data?.api_key_events ?? 0)}
          />
        </section>

        <section className="overflow-hidden rounded-3xl border border-border bg-background">
          <div className="flex flex-col gap-3 border-b border-border px-5 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-base font-semibold">{FILTERS[mode].label} access stream</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {formatNumber(logs.data?.total ?? 0)} matching events, newest first.
              </p>
            </div>
            <Button
              disabled={logs.isFetching}
              onClick={() => {
                void logs.refetch();
                void overview.refetch();
              }}
              size="sm"
              variant="outline"
            >
              <RefreshCw className={cn("size-4", logs.isFetching && "animate-spin")} />
              Refresh
            </Button>
          </div>

          {logs.isPending ? (
            <div className="px-5 py-10">
              <Spinner />
            </div>
          ) : (logs.data?.entries.length ?? 0) === 0 ? (
            <div className="px-5 py-10 text-sm text-muted-foreground">
              No access events match this view.
            </div>
          ) : (
            <AccessLogTable entries={logs.data?.entries ?? []} />
          )}
        </section>
      </div>
    </div>
  );
};

const AccessRadar = ({
  overview,
  pending,
}: {
  overview: AccessLogOverview | undefined;
  pending: boolean;
}) => {
  const buckets = overview?.by_status ?? [];
  const max = Math.max(1, ...buckets.map((bucket) => bucket.count));
  if (pending) return <Spinner />;
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-white/60">Status shape</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">
            {(overview?.error_rate ?? 0).toFixed(1)}%
          </div>
        </div>
        <Badge variant={(overview?.error_rate ?? 0) > 5 ? "warning" : "success"}>error rate</Badge>
      </div>
      <div className="mt-5 space-y-3">
        {buckets.length === 0 ? (
          <div className="text-sm text-white/60">Waiting for access events</div>
        ) : (
          buckets.map((bucket) => (
            <div key={bucket.label}>
              <div className="mb-1 flex items-center justify-between text-xs font-semibold">
                <span>{bucket.label}</span>
                <span>{formatNumber(bucket.count)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/10">
                <div
                  className={cn(
                    "h-full rounded-full",
                    bucket.label.startsWith("2") ? "bg-success" : "bg-warning",
                  )}
                  style={{ width: `${Math.max(5, (bucket.count / max) * 100)}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const Stat = ({
  icon: Icon,
  label,
  tone,
  value,
}: {
  icon: LucideIcon;
  label: string;
  tone?: "success" | "warning";
  value: string;
}) => (
  <div className="rounded-3xl border border-border bg-background p-4">
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      <Icon
        className={cn(
          "size-4 text-muted-foreground",
          tone === "success" && "text-success",
          tone === "warning" && "text-warning",
        )}
      />
    </div>
    <div className="mt-3 text-2xl font-semibold tabular-nums">{value}</div>
  </div>
);

const AccessLogTable = ({ entries }: { entries: AccessLogEntry[] }) => {
  const reduced = useReducedMotion();
  return (
    <div className="divide-y divide-border">
      {entries.map((entry, index) => (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="grid gap-4 px-5 py-4 transition-colors hover:bg-muted/60 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_12rem_9rem]"
          initial={reduced ? false : { opacity: 0, y: 8 }}
          key={entry.id}
          transition={{ delay: reduced ? 0 : Math.min(index, 8) * 0.025, duration: 0.18 }}
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge entry={entry} />
              <span className="truncate text-sm font-semibold">{entry.action}</span>
            </div>
            <div className="mt-1 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
              <Database className="size-3.5 shrink-0" />
              <span className="truncate">{entry.collection_name ?? entry.resource_type}</span>
            </div>
          </div>

          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{entry.path}</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <MetaPill>{entry.method}</MetaPill>
              <MetaPill>{entry.auth_method ?? "anonymous"}</MetaPill>
              {entry.route && <MetaPill>{entry.route}</MetaPill>}
            </div>
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold">
              {entry.api_key_id ? (
                <KeyRound className="size-4" />
              ) : (
                <UserRound className="size-4" />
              )}
              <span className="truncate">
                {entry.api_key_name ?? entry.actor_email ?? "anonymous"}
              </span>
            </div>
            <div className="mt-1 truncate text-xs text-muted-foreground">{entry.ip ?? "no ip"}</div>
          </div>

          <div className="flex items-center justify-between gap-4 xl:justify-end">
            <div className="text-right">
              <div className="flex items-center justify-end gap-1 text-sm font-semibold tabular-nums">
                <Clock3 className="size-3.5 text-muted-foreground" />
                {formatNumber(Math.round(entry.latency_ms))} ms
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {formatRelative(entry.created_at)}
              </div>
            </div>
            <Link
              className="flex size-9 shrink-0 items-center justify-center rounded-full border border-border transition-colors hover:bg-background"
              href={
                entry.collection_name
                  ? `/collections/${encodeURIComponent(entry.collection_name)}`
                  : "#"
              }
              title={entry.collection_name ? "Open collection" : "No collection context"}
            >
              <ArrowDownRight className="size-4" />
            </Link>
          </div>
        </motion.div>
      ))}
    </div>
  );
};

const StatusBadge = ({ entry }: { entry: AccessLogEntry }) => (
  <Badge variant={entry.success ? "success" : "error"}>{entry.status_code}</Badge>
);

const MetaPill = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex h-6 max-w-full items-center rounded-full bg-muted px-2 text-xs font-semibold text-muted-foreground">
    <span className="truncate">{children}</span>
  </span>
);

export default AccessLogsPage;
