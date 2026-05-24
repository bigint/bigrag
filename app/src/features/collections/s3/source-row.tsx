import { FolderSync, RefreshCw, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import {
  clampSyncProgress,
  intervalOptions,
  isActiveS3SyncJob,
  sourceStatusVariant,
  syncProgressForJob,
  syncStatusLabel,
} from "@/features/collections/s3-connector-utils";
import { formatRelative } from "@/lib/format";
import type { S3Source, S3SyncJob } from "@/types/bigrag";

export const SourceRow = ({
  isDeleting,
  job,
  offlineReason,
  onDelete,
  onSync,
  onToggleSchedule,
  onChangeInterval,
  source,
  syncPending,
  updatePending,
  workerOffline,
}: {
  isDeleting: boolean;
  job: S3SyncJob | undefined;
  offlineReason?: string;
  onDelete: () => void;
  onSync: (sourceId: string) => void;
  onToggleSchedule: (sourceId: string, enabled: boolean) => void;
  onChangeInterval: (sourceId: string, hours: number) => void;
  source: S3Source;
  syncPending: boolean;
  updatePending: boolean;
  workerOffline?: boolean;
}) => {
  const progress = job ? syncProgressForJob(job) : undefined;
  const isSyncing = source.status === "syncing" || isActiveS3SyncJob(job);
  return (
    <li className="flex flex-col gap-3 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <FolderSync className="size-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm font-semibold">{source.root_name}</span>
            <Badge dot variant={sourceStatusVariant[source.status]}>
              {source.status}
            </Badge>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{source.region}</span>
            {source.prefix && <span>{source.prefix}</span>}
            {source.last_sync_at && <span>last {formatRelative(source.last_sync_at)}</span>}
            {source.next_sync_at && <span>next {formatRelative(source.next_sync_at)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip content={workerOffline ? offlineReason : "Sync now"}>
            <Button
              aria-label="Sync source"
              disabled={syncPending || isSyncing || workerOffline}
              onClick={() => onSync(source.id)}
              size="icon"
              title={workerOffline ? offlineReason : undefined}
              variant="outline"
            >
              <RefreshCw className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Remove source">
            <Button
              aria-label="Remove source"
              disabled={isDeleting}
              onClick={onDelete}
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
              {syncStatusLabel(progress)}
            </span>
            <span className="font-semibold">{clampSyncProgress(progress.progress_percent)}%</span>
          </div>
          <div className="mt-2">
            <ProgressBar
              fillClassName="rounded-full"
              value={clampSyncProgress(progress.progress_percent)}
            />
          </div>
        </div>
      )}
      {source.last_error && <div className="text-xs text-destructive">{source.last_error}</div>}
      <div className="flex flex-wrap items-center gap-3">
        <Switch
          checked={source.schedule_enabled}
          disabled={updatePending}
          label="Scheduled"
          onCheckedChange={(checked) => onToggleSchedule(source.id, checked)}
        />
        <Select
          className="w-36"
          disabled={updatePending || !source.schedule_enabled}
          onChange={(value) => onChangeInterval(source.id, Number(value))}
          options={intervalOptions}
          value={String(source.sync_interval_hours)}
        />
      </div>
    </li>
  );
};
