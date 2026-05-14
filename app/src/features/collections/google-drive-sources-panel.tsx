import { FolderSync, RefreshCw, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { intervalOptions, statusVariant } from "@/features/collections/google-drive-panel.utils";
import {
  clampGoogleSyncProgress,
  googleSyncProgressForJob,
  googleSyncProgressLabel,
  isActiveGoogleSyncJob,
} from "@/features/collections/google-drive-progress";
import { ProgressBar } from "@/features/collections/google-drive-sync-monitor";
import type {
  useDeleteGoogleSource,
  useSyncGoogleSource,
  useUpdateGoogleSource,
} from "@/hooks/use-google-drive";
import { formatRelative } from "@/lib/format";
import type { GoogleDriveSource, GoogleDriveSyncJob } from "@/types/bigrag";

export const SourcesPanel = ({
  deleteSource,
  jobsBySource,
  sources,
  sourcesPending,
  syncSource,
  updateSource,
}: {
  deleteSource: ReturnType<typeof useDeleteGoogleSource>;
  jobsBySource: Map<string, GoogleDriveSyncJob>;
  sources: GoogleDriveSource[];
  sourcesPending: boolean;
  syncSource: ReturnType<typeof useSyncGoogleSource>;
  updateSource: ReturnType<typeof useUpdateGoogleSource>;
}) => (
  <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
    <div className="flex items-center justify-between border-border border-b px-4 py-3">
      <h3 className="text-sm font-semibold">Sources</h3>
      {sourcesPending && <Spinner />}
    </div>
    {sources.length ? (
      <ul className="max-h-[640px] divide-y divide-border overflow-y-auto">
        {sources.map((source) => (
          <SourceRow
            deleteSource={deleteSource}
            job={jobsBySource.get(source.id)}
            key={source.id}
            source={source}
            syncSource={syncSource}
            updateSource={updateSource}
          />
        ))}
      </ul>
    ) : (
      <Empty
        bordered={false}
        className="py-12"
        description="Selected Drive files and folders appear here."
        icon={<FolderSync className="size-5" />}
        title="No Drive sources"
      />
    )}
  </section>
);

const SourceRow = ({
  deleteSource,
  job,
  source,
  syncSource,
  updateSource,
}: {
  deleteSource: ReturnType<typeof useDeleteGoogleSource>;
  job: GoogleDriveSyncJob | undefined;
  source: GoogleDriveSource;
  syncSource: ReturnType<typeof useSyncGoogleSource>;
  updateSource: ReturnType<typeof useUpdateGoogleSource>;
}) => {
  const progress = job ? googleSyncProgressForJob(job) : undefined;
  const isSyncing = source.status === "syncing" || isActiveGoogleSyncJob(job);
  return (
    <li className="flex flex-col gap-3 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <FolderSync className="size-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm font-semibold">{source.root_name}</span>
            <Badge dot variant={statusVariant[source.status]}>
              {source.status}
            </Badge>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{source.source_type}</span>
            {source.last_sync_at && <span>last {formatRelative(source.last_sync_at)}</span>}
            {source.next_sync_at && <span>next {formatRelative(source.next_sync_at)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip content="Sync now">
            <Button
              aria-label="Sync source"
              disabled={syncSource.isPending || isSyncing}
              onClick={() => syncSource.mutate(source.id)}
              size="icon"
              variant="outline"
            >
              <RefreshCw className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Remove source">
            <Button
              aria-label="Remove source"
              disabled={deleteSource.isPending}
              onClick={() => deleteSource.mutate(source.id)}
              size="icon"
              variant="ghost"
            >
              <Trash2 className="size-4" />
            </Button>
          </Tooltip>
        </div>
      </div>
      {progress && (
        <div className="rounded-sm border border-border bg-background p-3">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="min-w-0 truncate text-muted-foreground">
              {googleSyncProgressLabel(progress)}
            </span>
            <span className="font-semibold">
              {clampGoogleSyncProgress(progress.progress_percent)}%
            </span>
          </div>
          <div className="mt-2">
            <ProgressBar compact progress={progress} />
          </div>
        </div>
      )}
      {source.last_error && <div className="text-xs text-destructive">{source.last_error}</div>}
      <div className="flex flex-wrap items-center gap-3">
        <Switch
          checked={source.schedule_enabled}
          disabled={updateSource.isPending}
          label="Scheduled"
          onCheckedChange={(checked) =>
            updateSource.mutate({
              body: { schedule_enabled: checked },
              sourceId: source.id,
            })
          }
        />
        <Select
          className="w-36"
          disabled={updateSource.isPending || !source.schedule_enabled}
          onChange={(value) =>
            updateSource.mutate({
              body: { sync_interval_hours: Number(value) },
              sourceId: source.id,
            })
          }
          options={intervalOptions}
          value={String(source.sync_interval_hours)}
        />
      </div>
    </li>
  );
};
