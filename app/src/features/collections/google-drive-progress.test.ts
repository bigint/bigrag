import { describe, expect, it } from "vitest";
import type { GoogleDriveSyncJob } from "@/types/bigrag";
import {
  clampGoogleSyncProgress,
  googleSyncCountLabel,
  googleSyncProgressForJob,
  googleSyncProgressLabel,
  isActiveGoogleSyncJob,
} from "./google-drive-progress";

const job = (overrides: Partial<GoogleDriveSyncJob> = {}): GoogleDriveSyncJob => ({
  completed_at: null,
  created_at: "2026-05-11T00:00:00Z",
  details: {},
  error_message: null,
  id: "job_1",
  provider: "google_drive",
  source_id: "source_1",
  started_at: "2026-05-11T00:00:00Z",
  status: "running",
  total_created: 1,
  total_deleted: 0,
  total_failed: 0,
  total_found: 4,
  total_skipped: 1,
  total_updated: 1,
  trigger: "manual",
  updated_at: "2026-05-11T00:00:00Z",
  ...overrides,
});

describe("google-drive-progress", () => {
  it("uses backend progress details when present", () => {
    const progress = googleSyncProgressForJob(
      job({
        details: {
          progress: {
            counts: { created: 2, deleted: 0, failed: 0, skipped: 1, updated: 0 },
            current_item_id: "file_1",
            current_item_name: "Roadmap.pdf",
            message: "Syncing Roadmap.pdf",
            phase: "syncing",
            processed_items: 3,
            progress_percent: 68,
            total_items: 5,
          },
        },
      }),
    );

    expect(progress.progress_percent).toBe(68);
    expect(googleSyncProgressLabel(progress)).toBe("Syncing Roadmap.pdf");
    expect(googleSyncCountLabel(progress)).toBe("3 of 5");
  });

  it("falls back to job totals for older responses", () => {
    const progress = googleSyncProgressForJob(job({ status: "complete" }));

    expect(progress.phase).toBe("complete");
    expect(progress.progress_percent).toBe(100);
    expect(progress.counts.created).toBe(1);
    expect(isActiveGoogleSyncJob(job({ status: "running" }))).toBe(true);
    expect(isActiveGoogleSyncJob(job({ status: "complete" }))).toBe(false);
  });

  it("formats zero and out-of-range progress values", () => {
    const progress = googleSyncProgressForJob(
      job({
        total_created: 0,
        total_deleted: 0,
        total_failed: 0,
        total_found: 0,
        total_skipped: 0,
        total_updated: 0,
      }),
    );

    expect(googleSyncCountLabel(progress)).toBe("No Drive files found");
    expect(clampGoogleSyncProgress(140)).toBe(100);
    expect(clampGoogleSyncProgress(-5)).toBe(0);
  });
});
