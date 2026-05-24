import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import { Activity, ArrowUpRight, Gauge, Radio, ShieldCheck, SignalHigh } from "lucide-react";
import { Panel } from "@/components/ui/panel";
import { Spinner } from "@/components/ui/spinner";
import { clampPercent, formatMs, formatPercent } from "@/features/overview/overview-helpers";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import type { AccessLogOverview } from "@/types/bigrag";

export const AccessCommandCenter = ({
  overview,
  pending,
}: {
  overview: AccessLogOverview | undefined;
  pending: boolean;
}) => {
  const quiet = !pending && (!overview || overview.total_events === 0);

  return (
    <Panel className="overflow-hidden p-0">
      <div className="border-b border-border px-5 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-2xl border border-border bg-muted text-foreground">
              <Activity className="size-4" />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold">Access telemetry</h2>
              <p className="mt-1 truncate text-sm text-muted-foreground">
                Last {overview?.window_days ?? 7} days of query traffic, outcomes, and latency.
              </p>
            </div>
          </div>
          <Link
            to="/access-logs"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-semibold hover:bg-muted"
          >
            Open logs
            <ArrowUpRight className="size-3.5" />
          </Link>
        </div>
      </div>

      {pending ? (
        <div className="px-5 py-8">
          <Spinner />
        </div>
      ) : quiet ? (
        <div className="px-5 py-8 text-sm text-muted-foreground">
          No access events have landed in this window yet.
        </div>
      ) : (
        <div>
          <div className="grid gap-px bg-border lg:grid-cols-[minmax(18rem,1.25fr)_repeat(3,minmax(0,0.75fr))]">
            <AccessHealthTile overview={overview} />
            <AccessKpiCell
              icon={Radio}
              label="Events"
              sub={`${formatNumber(overview?.query_events ?? 0)} query events`}
              value={formatNumber(overview?.total_events ?? 0)}
            />
            <AccessKpiCell
              icon={Gauge}
              label="P95 latency"
              sub={`${formatMs(overview?.avg_latency_ms)} average`}
              tone="warning"
              value={formatMs(overview?.p95_latency_ms)}
            />
            <AccessKpiCell
              icon={ShieldCheck}
              label="Actors"
              sub="distinct users"
              value={formatNumber(overview?.unique_users ?? 0)}
            />
          </div>
        </div>
      )}
    </Panel>
  );
};

const AccessHealthTile = ({ overview }: { overview: AccessLogOverview | undefined }) => {
  const totalEvents = overview?.total_events ?? 0;
  const successRate = clampPercent(overview?.success_rate);
  const errorRate = clampPercent(overview?.error_rate);
  const errorEvents = Math.round(totalEvents * (errorRate / 100));

  return (
    <div className="bg-muted/50 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
            <SignalHigh className="size-3.5 text-success" />
            <span>Access health</span>
          </div>
          <div className="mt-3 text-5xl font-semibold leading-none text-foreground tabular-nums">
            {formatPercent(overview?.success_rate)}
          </div>
        </div>
        <span className="rounded-full bg-background px-2.5 py-1 text-xs font-semibold text-muted-foreground">
          {overview?.window_days ?? 7}d
        </span>
      </div>

      <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-background">
        <div className="bg-success" style={{ width: `${successRate}%` }} />
        <div className="bg-destructive" style={{ width: `${errorRate}%` }} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-xs font-semibold text-muted-foreground">
        <div>
          <div className="text-foreground">{formatNumber(totalEvents)}</div>
          total events
        </div>
        <div>
          <div className="text-foreground">{formatNumber(errorEvents)}</div>
          failed requests
        </div>
      </div>
    </div>
  );
};

const AccessKpiCell = ({
  icon: Icon,
  label,
  sub,
  tone,
  value,
}: {
  icon: LucideIcon;
  label: string;
  sub: string;
  tone?: "success" | "warning";
  value: string;
}) => (
  <div className="min-w-0 bg-background p-5">
    <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
      <Icon
        className={cn(
          "size-3.5",
          tone === "success" && "text-success",
          tone === "warning" && "text-warning",
        )}
      />
      <span className="truncate">{label}</span>
    </div>
    <div className="mt-3 truncate text-3xl font-semibold tabular-nums">{value}</div>
    <div className="mt-1 truncate text-xs font-semibold text-muted-foreground">{sub}</div>
  </div>
);
