import { describe, expect, it } from "vitest";
import { formatHeartbeatAge, getWorkerAvailability, workerOfflineActionMessage } from "./worker-status";

describe("worker status", () => {
  it("treats missing worker stats as unknown", () => {
    const availability = getWorkerAvailability(undefined);

    expect(availability.state).toBe("unknown");
    expect(availability.offline).toBe(false);
    expect(availability.message).toContain("stay available");
  });

  it("derives the online state from a recent heartbeat", () => {
    const availability = getWorkerAvailability({
      workers: {
        online: true,
        heartbeat_age_seconds: 4,
        heartbeat_at: "2026-05-15T12:00:00+00:00",
      },
    });

    expect(availability.state).toBe("online");
    expect(availability.heartbeatAgeLabel).toBe("4 seconds ago");
  });

  it("derives the offline state from a stale heartbeat", () => {
    const availability = getWorkerAvailability({
      workers: {
        online: false,
        heartbeat_age_seconds: 181,
        heartbeat_at: "2026-05-15T11:57:00+00:00",
      },
    });

    expect(availability.state).toBe("offline");
    expect(availability.title).toBe("bigrag-worker is offline");
    expect(workerOfflineActionMessage(availability)).toContain(
      "Queued work will not run until the worker is started.",
    );
    expect(workerOfflineActionMessage(availability)).toContain("Last heartbeat 3 minutes ago.");
  });

  it("keeps missing heartbeat age readable", () => {
    const availability = getWorkerAvailability({
      workers: {
        online: false,
        heartbeat_age_seconds: null,
        heartbeat_at: null,
      },
    });

    expect(availability.offline).toBe(true);
    expect(availability.heartbeatAgeLabel).toBeNull();
  });

  it("formats heartbeat ages", () => {
    expect(formatHeartbeatAge(1)).toBe("1 second ago");
    expect(formatHeartbeatAge(65)).toBe("1 minute ago");
    expect(formatHeartbeatAge(3600)).toBe("1 hour ago");
    expect(formatHeartbeatAge(172_800)).toBe("2 days ago");
  });
});
