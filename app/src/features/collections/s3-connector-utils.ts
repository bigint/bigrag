import type { ConnectorSyncProgress, S3Source, S3SyncJob } from "@/types/bigrag";

export const sourceStatusVariant: Record<S3Source["status"], "success" | "info" | "error"> = {
  error: "error",
  idle: "success",
  syncing: "info",
};

export const jobStatusVariant: Record<
  S3SyncJob["status"],
  "success" | "warning" | "info" | "error"
> = {
  complete: "success",
  failed: "error",
  pending: "warning",
  running: "info",
};

export const intervalOptions = [
  { label: "Hourly", value: "1" },
  { label: "Daily", value: "24" },
  { label: "Weekly", value: "168" },
] as const;

export const activeS3SyncStatuses = new Set<S3SyncJob["status"]>(["pending", "running"]);

export const isActiveS3SyncJob = (job: S3SyncJob | undefined) =>
  Boolean(job && activeS3SyncStatuses.has(job.status));

export const syncProgressForJob = (job: S3SyncJob): ConnectorSyncProgress => {
  const progress = job.details.progress;
  if (progress) return progress;
  const phase =
    job.status === "complete" ? "complete" : job.status === "failed" ? "failed" : "syncing";
  const processed =
    job.total_created +
    job.total_updated +
    job.total_skipped +
    job.total_deleted +
    job.total_failed;
  const total = Math.max(job.total_found + job.total_deleted, processed);
  return {
    counts: {
      created: job.total_created,
      deleted: job.total_deleted,
      failed: job.total_failed,
      skipped: job.total_skipped,
      updated: job.total_updated,
    },
    current_item_id: null,
    current_item_name: null,
    message:
      job.error_message ??
      (job.status === "complete"
        ? "S3 sync complete. Documents queued for ingestion."
        : "S3 sync running"),
    phase,
    processed_items: processed,
    progress_percent: job.status === "complete" || job.status === "failed" ? 100 : 15,
    total_items: total,
  };
};

export const clampSyncProgress = (value: number) => Math.max(0, Math.min(100, Math.round(value)));

export const syncStatusLabel = (progress: ConnectorSyncProgress) => {
  const count = `${progress.processed_items.toLocaleString()} of ${progress.total_items.toLocaleString()}`;
  const hasCount = progress.total_items > 0;
  switch (progress.phase) {
    case "queued":
      return "Sync queued";
    case "authenticating":
      return "Connecting to S3";
    case "scanning":
      return "Scanning S3 objects";
    case "syncing":
      return hasCount ? `Syncing ${count} remote files` : "Syncing remote files";
    case "removing":
      return hasCount ? `Removing ${count} missing files` : "Checking for removed files";
    case "finalizing":
      return "Finalizing sync";
    case "complete":
      return hasCount ? `Synced ${count} remote files` : "Sync complete";
    case "failed":
      return "Sync failed";
  }
};
