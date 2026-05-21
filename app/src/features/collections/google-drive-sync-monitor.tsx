import { HardDriveDownload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { jobVariant } from "@/features/collections/google-drive-panel.utils";
import {
  clampGoogleSyncProgress,
  googleSyncCountLabel,
  googleSyncProgressForJob,
  googleSyncProgressLabel,
} from "@/features/collections/google-drive-progress";
import { cn } from "@/lib/cn";
import type { GoogleDriveSyncJob, GoogleSyncProgress } from "@/types/bigrag";

export const SyncMonitor = ({
  isPending,
  job,
  streaming,
}: {
  isPending: boolean;
  job: GoogleDriveSyncJob | undefined;
  streaming: boolean;
}) => {
  if (isPending) {
    return (
      <section className="rounded-sm border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Sync monitor</h3>
          <Spinner />
        </div>
      </section>
    );
  }
  if (!job) {
    return (
      <section className="rounded-sm border border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border">
            <HardDriveDownload className="size-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">Sync monitor</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">No sync jobs yet</p>
          </div>
        </div>
      </section>
    );
  }

  const progress = googleSyncProgressForJob(job);
  return (
    <section className="rounded-sm border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Sync monitor</h3>
            {streaming && <span className="size-1.5 rounded-full bg-success" />}
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {googleSyncProgressLabel(progress)}
          </p>
        </div>
        <Badge dot variant={jobVariant[job.status]}>
          {job.status}
        </Badge>
      </div>
      <div className="mt-4">
        <ProgressBar progress={progress} />
      </div>
      <SyncCounters progress={progress} />
      {job.error_message && (
        <div className="mt-3 text-xs text-destructive">{job.error_message}</div>
      )}
    </section>
  );
};

export const ProgressBar = ({
  compact = false,
  progress,
}: {
  compact?: boolean;
  progress: GoogleSyncProgress;
}) => {
  const value = clampGoogleSyncProgress(progress.progress_percent);
  return (
    <div>
      <div
        aria-label="Sync progress"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={value}
        className={cn("h-2 overflow-hidden rounded-full bg-muted", compact && "h-1.5")}
        role="progressbar"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} />
      </div>
      {!compact && (
        <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>{googleSyncCountLabel(progress)}</span>
          <span className="font-semibold text-foreground">{value}%</span>
        </div>
      )}
    </div>
  );
};

const SyncCounters = ({ progress }: { progress: GoogleSyncProgress }) => {
  const counts = [
    ["Created", progress.counts.created],
    ["Updated", progress.counts.updated],
    ["Skipped", progress.counts.skipped],
    ["Deleted", progress.counts.deleted],
    ["Failed", progress.counts.failed],
  ] as const;
  return (
    <div className="mt-4 grid grid-cols-5 gap-2">
      {counts.map(([label, value]) => (
        <div
          className="rounded-sm border border-border bg-background px-2 py-2 text-center"
          key={label}
        >
          <div className="text-sm font-semibold">{value.toLocaleString()}</div>
          <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{label}</div>
        </div>
      ))}
    </div>
  );
};
