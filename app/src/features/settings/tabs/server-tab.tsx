import { getWorkerAvailability } from "@/features/workers/worker-status";
import { usePlatformStats, useReadiness } from "@/hooks/use-platform";
import { cn } from "@/lib/cn";

type Status = "ok" | "degraded" | "down" | "unknown";

const statusOf = (ok: boolean | undefined): Status => {
  if (ok === undefined) return "unknown";
  return ok ? "ok" : "down";
};

const statusFromHealth = (status: "ok" | "degraded" | "down" | undefined): Status =>
  status ?? "unknown";

const StatusPill = ({ status }: { status: Status }) => {
  const map = {
    ok: { dotColor: "bg-success", label: "Operational", text: "text-success" },
    degraded: { dotColor: "bg-warning", label: "Degraded", text: "text-warning" },
    down: { dotColor: "bg-destructive", label: "Down", text: "text-destructive" },
    unknown: {
      dotColor: "bg-muted-foreground/40",
      label: "Unknown",
      text: "text-muted-foreground",
    },
  } as const;
  const tone = map[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", tone.text)}>
      <span className={cn("size-1.5 rounded-full", tone.dotColor)} />
      {tone.label}
    </span>
  );
};

const HealthRow = ({
  label,
  ok,
  hint,
}: {
  label: string;
  ok: boolean | undefined;
  hint?: string | null;
}) => (
  <div className="flex items-center justify-between gap-3 px-4 py-3">
    <div className="min-w-0">
      <div className="text-sm font-semibold text-foreground">{label}</div>
      {hint && <div className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</div>}
    </div>
    <StatusPill status={statusOf(ok)} />
  </div>
);

const MetricRow = ({ label, value }: { label: string; value: string | number }) => (
  <div className="flex items-center justify-between gap-3 px-4 py-3">
    <span className="text-sm font-semibold text-foreground">{label}</span>
    <span className="text-xs font-semibold tabular-nums text-muted-foreground">{value}</span>
  </div>
);

const EnvRow = ({ label, value }: { label: string; value: string }) => (
  <div className="flex items-center justify-between gap-3 px-4 py-3">
    <code className="font-mono text-xs text-foreground">{label}</code>
    <span className="truncate text-xs text-muted-foreground">{value}</span>
  </div>
);

const ENV_ROWS: ReadonlyArray<{ label: string; value: string }> = [
  { label: "Postgres", value: "BIGRAG_DATABASE_URL" },
  { label: "Redis", value: "BIGRAG_REDIS_URL" },
  { label: "Vector store", value: "Admin Settings / Vector store" },
  { label: "Encryption", value: "BIGRAG_MASTER_KEY" },
  { label: "Bind address", value: "BIGRAG_HOST / BIGRAG_PORT" },
  { label: "Split admin UI", value: "admin UI backend URL" },
];

const QUEUE_REASON_LABELS: Readonly<Record<string, string>> = {
  dead_lettered_jobs: "dead-lettered jobs",
  retrying_jobs: "jobs retrying",
  stale_processing_jobs: "stale processing jobs",
  worker_offline: "worker offline",
  worker_offline_with_active_queue: "worker offline with active queue",
};

const queueReasonText = (reasons: readonly string[] | undefined) => {
  if (!reasons?.length) return "No queue risks detected.";
  return reasons.map((reason) => QUEUE_REASON_LABELS[reason] ?? reason).join(", ");
};

export const ServerTab = () => {
  const { data: readiness, error } = useReadiness();
  const { data: stats } = usePlatformStats();
  const overallStatus = readiness ? statusOf(readiness.status === "ok") : "unknown";
  const version = readiness?.version;
  const workerAvailability = getWorkerAvailability(stats);
  const queueHealth = stats?.queue_health;

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-md border border-border bg-card">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/35 p-4">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold tracking-normal">System health</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {readiness
                ? `bigRAG v${version}`
                : error
                  ? "Could not reach the API."
                  : "Checking readiness…"}
            </p>
          </div>
          <StatusPill status={overallStatus} />
        </header>
        <div className="divide-y divide-border">
          <HealthRow label="Postgres" ok={readiness?.postgres} hint={readiness?.postgres_error} />
          <HealthRow label="Redis" ok={readiness?.redis} hint={readiness?.redis_error} />
          <HealthRow
            label={
              readiness?.vector_store_provider
                ? `Vector store · ${readiness.vector_store_provider.replace("_", " ")}`
                : "Vector store"
            }
            ok={readiness?.vector_store}
            hint={readiness?.vector_store_error}
          />
          <HealthRow
            label="Embeddings"
            ok={readiness?.embedding}
            hint={
              readiness?.embedding_error ??
              (readiness?.embedding_source === "preset"
                ? "via embedding preset"
                : readiness?.embedding_source === "collection"
                  ? "via collection-level key"
                  : null)
            }
          />
        </div>
      </section>

      <section className="rounded-md border border-border bg-card">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/35 p-4">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold tracking-normal">Worker and queue</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {queueReasonText(queueHealth?.reasons)}
            </p>
          </div>
          <StatusPill status={statusFromHealth(queueHealth?.status)} />
        </header>
        <div className="divide-y divide-border">
          <HealthRow
            label="Worker"
            ok={workerAvailability.unknown ? undefined : workerAvailability.online}
            hint={
              workerAvailability.heartbeatAgeLabel
                ? `heartbeat ${workerAvailability.heartbeatAgeLabel}`
                : workerAvailability.message
            }
          />
          <MetricRow label="Pending" value={stats?.queue.pending ?? 0} />
          <MetricRow label="Processing" value={stats?.queue.processing ?? 0} />
          <MetricRow label="Retrying" value={stats?.queue.retrying ?? 0} />
          <MetricRow label="Dead-lettered" value={stats?.queue.dead_lettered ?? 0} />
          <MetricRow label="Stale processing" value={stats?.queue.stale_processing ?? 0} />
        </div>
      </section>

      <section className="rounded-md border border-border bg-card">
        <header className="flex flex-col gap-1 border-b border-border bg-muted/35 p-4">
          <h3 className="text-sm font-semibold tracking-normal">Bootstrap wiring</h3>
          <p className="text-xs text-muted-foreground">
            These coordinates must exist before the API can read database-backed settings.
          </p>
        </header>
        <div className="divide-y divide-border">
          {ENV_ROWS.map((row) => (
            <EnvRow key={row.label} label={row.label} value={row.value} />
          ))}
        </div>
      </section>
    </div>
  );
};
