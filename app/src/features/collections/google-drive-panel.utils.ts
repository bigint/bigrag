import type { GoogleDriveSource, GoogleDriveSyncJob } from "@/types/bigrag";

export const statusVariant: Record<
  GoogleDriveSource["status"],
  "success" | "warning" | "info" | "error"
> = {
  error: "error",
  idle: "success",
  needs_reauth: "warning",
  syncing: "info",
};

export const jobVariant: Record<
  GoogleDriveSyncJob["status"],
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
