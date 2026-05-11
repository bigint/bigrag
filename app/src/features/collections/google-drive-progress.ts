import type { GoogleDriveSyncJob, GoogleSyncProgress } from "@/types/bigrag";

export const activeGoogleSyncStatuses = new Set<GoogleDriveSyncJob["status"]>([
  "pending",
  "running",
]);

export const isActiveGoogleSyncJob = (job: GoogleDriveSyncJob | undefined) =>
  Boolean(job && activeGoogleSyncStatuses.has(job.status));

export const googleSyncProgressForJob = (job: GoogleDriveSyncJob): GoogleSyncProgress => {
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
        ? "Drive sync complete. Documents queued for ingestion."
        : "Google Drive sync running"),
    phase,
    processed_items: processed,
    progress_percent: job.status === "complete" || job.status === "failed" ? 100 : 15,
    total_items: total,
  };
};

export const clampGoogleSyncProgress = (value: number) =>
  Math.max(0, Math.min(100, Math.round(value)));

export const googleSyncCountLabel = (progress: GoogleSyncProgress) => {
  if (progress.total_items <= 0) return "No Drive files found";
  return `${progress.processed_items.toLocaleString()} of ${progress.total_items.toLocaleString()}`;
};

export const googleSyncProgressLabel = (progress: GoogleSyncProgress) => {
  const item =
    progress.current_item_name && !progress.message.includes(progress.current_item_name)
      ? `: ${progress.current_item_name}`
      : "";
  return `${progress.message}${item}`;
};
