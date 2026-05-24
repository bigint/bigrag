import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";

interface DocumentReadinessPanelProps {
  readonly ready: number;
  readonly processing: number;
  readonly pending: number;
  readonly failed: number;
  readonly total: number;
  readonly readyPct: number;
  readonly failedPct: number;
}

export const DocumentReadinessPanel = ({
  ready,
  processing,
  pending,
  failed,
  total,
  readyPct,
  failedPct,
}: DocumentReadinessPanelProps) => (
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
        failed={failed}
        pending={pending}
        processing={processing}
        ready={ready}
        total={total}
      />
      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        <StatusCount label="Ready" value={ready} tone="success" />
        <StatusCount label="Processing" value={processing} tone="info" />
        <StatusCount label="Pending" value={pending} tone="warning" />
        <StatusCount label="Failed" value={failed} tone="error" />
      </div>
    </div>
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
