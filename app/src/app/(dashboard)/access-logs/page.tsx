"use client";

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  Clock3,
  Database,
  KeyRound,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { TabButton } from "@/components/ui/tabs";
import { type AccessLogFilters, useAccessLogs, useAccessOverview } from "@/hooks/use-access-logs";
import { useSession } from "@/hooks/use-auth";
import { cn } from "@/lib/cn";
import { formatNumber, formatRelative } from "@/lib/format";
import type { AccessLogEntry } from "@/types/bigrag";

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
  const refresh = () => {
    void logs.refetch();
    void overview.refetch();
  };

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
    <div className="flex flex-col gap-5">
      <PageHeader
        actions={
          <Button disabled={logs.isFetching} onClick={refresh} size="sm" variant="outline">
            <RefreshCw className={cn("size-4", logs.isFetching && "animate-spin")} />
            Refresh
          </Button>
        }
        className="mb-0"
        description="Trace query, vector, and evaluation traffic by actor, outcome, and latency."
        title="Access logs"
      />

      <div className="flex flex-wrap gap-1.5">
        {Object.entries(FILTERS).map(([key, item]) => (
          <TabButton
            active={mode === key}
            icon={item.icon}
            key={key}
            label={item.label}
            onClick={() => setMode(key as LogMode)}
          />
        ))}
      </div>

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
        <div className="border-b border-border px-5 py-4">
          <div>
            <h2 className="text-base font-semibold">{FILTERS[mode].label} access stream</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatNumber(logs.data?.total ?? 0)} matching events, newest first.
            </p>
          </div>
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

          <div className="flex items-center justify-start gap-4 xl:justify-end">
            <div className="text-right">
              <div className="flex items-center justify-end gap-1 text-sm font-semibold tabular-nums">
                <Clock3 className="size-3.5 text-muted-foreground" />
                {formatNumber(Math.round(entry.latency_ms))} ms
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {formatRelative(entry.created_at)}
              </div>
            </div>
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
