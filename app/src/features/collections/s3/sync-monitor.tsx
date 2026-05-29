import { RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Empty } from "@/components/ui/empty";
import { ProgressBar } from "@/components/ui/progress-bar";
import { QueryError } from "@/components/ui/query-error";
import { Spinner } from "@/components/ui/spinner";
import {
  clampSyncProgress,
  jobStatusVariant,
  syncProgressForJob,
  syncStatusLabel,
} from "@/features/collections/s3-connector-utils";
import type { S3SyncJob } from "@/types/bigrag";

export const SyncMonitor = ({
  error,
  isError,
  isPending,
  job,
  onRetry,
}: {
  error: unknown;
  isError: boolean;
  isPending: boolean;
  job: S3SyncJob | undefined;
  onRetry: () => void;
}) => (
  <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
    <div className="flex items-center justify-between border-border border-b px-4 py-3">
      <h3 className="text-sm font-semibold">Sync monitor</h3>
    </div>
    {isError ? (
      <QueryError
        className="m-4"
        error={error}
        onRetry={onRetry}
        title="Sync jobs could not load"
      />
    ) : isPending ? (
      <div className="flex h-32 items-center justify-center">
        <Spinner />
      </div>
    ) : job ? (
      <SyncJobBody job={job} />
    ) : (
      <Empty
        bordered={false}
        className="py-10"
        description="Sync jobs appear here."
        icon={<RefreshCw className="size-5" />}
        title="No sync jobs"
      />
    )}
  </section>
);

const SyncJobBody = ({ job }: { job: S3SyncJob }) => {
  const progress = syncProgressForJob(job);
  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{syncStatusLabel(progress)}</div>
          {progress.current_item_name && (
            <div
              className="mt-1 truncate text-xs text-muted-foreground"
              title={progress.current_item_name}
            >
              {progress.current_item_name}
            </div>
          )}
        </div>
        <Badge dot variant={jobStatusVariant[job.status]}>
          {job.status}
        </Badge>
      </div>
      <ProgressBar
        fillClassName="rounded-full"
        value={clampSyncProgress(progress.progress_percent)}
      />
      <div className="grid grid-cols-3 gap-2 text-xs sm:grid-cols-5">
        <SyncCount label="Created" value={job.total_created} />
        <SyncCount label="Updated" value={job.total_updated} />
        <SyncCount label="Skipped" value={job.total_skipped} />
        <SyncCount label="Deleted" value={job.total_deleted} />
        <SyncCount label="Failed" value={job.total_failed} />
      </div>
    </div>
  );
};

const SyncCount = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-sm border border-border bg-background px-2 py-2">
    <div className="text-muted-foreground">{label}</div>
    <div className="mt-1 font-semibold">{value.toLocaleString()}</div>
  </div>
);
