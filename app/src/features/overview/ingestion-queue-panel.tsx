import { Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { queueHealthVariant } from "@/features/overview/overview-helpers";
import type { WorkerAvailability } from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { formatNumber } from "@/lib/format";

const QUEUE_REASON_LABELS: Readonly<Record<string, string>> = {
  dead_lettered_jobs: "Dead-lettered jobs need operator review.",
  retrying_jobs: "Some jobs are waiting to retry.",
  stale_processing_jobs: "Stale processing leases were detected.",
  worker_offline: "The worker heartbeat is offline.",
  worker_offline_with_active_queue: "The worker is offline while work is queued.",
};

interface IngestionQueuePanelProps {
  readonly queueItems: [string, number][];
  readonly queueStatus: string | undefined;
  readonly queueReasons: readonly string[] | undefined;
  readonly workerAvailability: WorkerAvailability;
}

export const IngestionQueuePanel = ({
  queueItems,
  queueStatus,
  queueReasons,
  workerAvailability,
}: IngestionQueuePanelProps) => (
  <Panel>
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold">Ingestion queue</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Work waiting behind document upload, backups, webhooks, and connector syncs.
        </p>
      </div>
      <Badge variant={queueHealthVariant(queueStatus)} dot>
        {queueStatus ?? "checking"}
      </Badge>
    </div>
    <WorkerOfflineBanner
      availability={workerAvailability}
      className="mt-4"
      compact
      message="Pending uploads, backups, webhooks, and connector syncs cannot drain until the worker is started."
    />
    <QueueHealthNote reasons={queueReasons} />
    <div className="mt-4 space-y-2">
      {queueItems.length === 0 ? (
        <div className="rounded-2xl border border-border bg-muted px-3 py-3 text-sm font-semibold">
          Queue is clear
        </div>
      ) : (
        queueItems.map(([label, value]) => <QueueRow key={label} label={label} value={value} />)
      )}
    </div>
  </Panel>
);

const QueueHealthNote = ({ reasons }: { reasons: readonly string[] | undefined }) => {
  if (!reasons?.length) return null;
  return (
    <div className="mt-4 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-xs font-semibold text-warning">
      {reasons.map((reason) => QUEUE_REASON_LABELS[reason] ?? reason).join(" ")}
    </div>
  );
};

const QueueRow = ({ label, value }: { label: string; value: number }) => (
  <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted/60 px-3 py-2.5">
    <div className="flex items-center gap-2">
      <Database className="size-4 text-muted-foreground" />
      <span className="text-sm font-semibold capitalize">{label.replaceAll("_", " ")}</span>
    </div>
    <span className="text-sm font-semibold tabular-nums">{formatNumber(value)}</span>
  </div>
);
