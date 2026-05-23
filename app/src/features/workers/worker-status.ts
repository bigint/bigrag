import type { PlatformStats, WorkerStats } from "@/types/bigrag";

type WorkerAvailabilityState = "online" | "offline" | "unknown";

export type WorkerAvailability = {
  online: boolean;
  offline: boolean;
  unknown: boolean;
  title: string;
  message: string;
  heartbeatAgeLabel: string | null;
};

const offlineMessage = "Queued work will not run until the worker is started.";

export const getWorkerAvailability = (
  stats: Pick<PlatformStats, "workers"> | undefined,
): WorkerAvailability => {
  if (!stats?.workers) {
    return workerAvailability("unknown", undefined);
  }
  return workerAvailability(stats.workers.online ? "online" : "offline", stats.workers);
};

export const workerOfflineActionMessage = (availability: WorkerAvailability) => {
  const lastHeartbeat = availability.heartbeatAgeLabel
    ? ` Last heartbeat ${availability.heartbeatAgeLabel}.`
    : "";
  return `${availability.title}. ${availability.message}${lastHeartbeat}`;
};

const workerAvailability = (
  state: WorkerAvailabilityState,
  workers: WorkerStats | undefined,
): WorkerAvailability => ({
  online: state === "online",
  offline: state === "offline",
  unknown: state === "unknown",
  title:
    state === "offline"
      ? "bigrag-worker is offline"
      : state === "online"
        ? "bigrag-worker is online"
        : "Worker status unavailable",
  message:
    state === "offline"
      ? offlineMessage
      : state === "online"
        ? "Queued work can be processed."
        : "Worker-dependent actions stay available until an offline heartbeat is confirmed.",
  heartbeatAgeLabel: formatHeartbeatAge(workers?.heartbeat_age_seconds ?? null),
});

const formatHeartbeatAge = (seconds: number | null) => {
  if (seconds === null) return null;
  if (seconds < 60) return `${seconds} second${seconds === 1 ? "" : "s"} ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
};
