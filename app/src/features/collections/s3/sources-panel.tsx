import { FolderSync, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { SourceRow } from "@/features/collections/s3/source-row";
import type { S3Source, S3SyncJob } from "@/types/bigrag";

export const SourcesPanel = ({
  addSourceDisabled,
  deletePending,
  jobsBySource,
  offlineReason,
  onAddSource,
  onChangeInterval,
  onDelete,
  onSync,
  onToggleSchedule,
  sources,
  sourcesPending,
  syncPending,
  updatePending,
  workerOffline,
}: {
  addSourceDisabled: boolean;
  deletePending: boolean;
  jobsBySource: Map<string, S3SyncJob>;
  offlineReason?: string;
  onAddSource: () => void;
  onChangeInterval: (sourceId: string, hours: number) => void;
  onDelete: (sourceId: string) => Promise<void>;
  onSync: (sourceId: string) => void;
  onToggleSchedule: (sourceId: string, enabled: boolean) => void;
  sources: S3Source[];
  sourcesPending: boolean;
  syncPending: boolean;
  updatePending: boolean;
  workerOffline?: boolean;
}) => {
  const [deleteFor, setDeleteFor] = useState<S3Source | null>(null);

  return (
    <>
      <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-border border-b bg-muted/35 px-4 py-4">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">Sources</h3>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {sources.length.toLocaleString()} configured
            </div>
          </div>
          <div className="flex items-center gap-2">
            {sourcesPending && <Spinner size="sm" />}
            <Tooltip content={workerOffline ? offlineReason : "Add source"}>
              <Button disabled={addSourceDisabled} onClick={onAddSource} size="sm">
                <Plus className="size-4" />
                Add source
              </Button>
            </Tooltip>
          </div>
        </div>
        {workerOffline && (
          <div className="border-border border-b bg-warning/10 px-4 py-3 text-xs text-warning">
            Scheduled syncs wait until bigrag-worker is online.
          </div>
        )}
        {sources.length ? (
          <ul className="max-h-[680px] divide-y divide-border overflow-y-auto">
            {sources.map((source) => (
              <SourceRow
                isDeleting={deletePending}
                job={jobsBySource.get(source.id)}
                key={source.id}
                offlineReason={offlineReason}
                onChangeInterval={onChangeInterval}
                onDelete={() => setDeleteFor(source)}
                onSync={onSync}
                onToggleSchedule={onToggleSchedule}
                source={source}
                syncPending={syncPending}
                updatePending={updatePending}
                workerOffline={workerOffline}
              />
            ))}
          </ul>
        ) : (
          <Empty
            bordered={false}
            className="py-12"
            action={
              <Button disabled={addSourceDisabled} onClick={onAddSource}>
                <Plus className="size-4" />
                Add source
              </Button>
            }
            description="Add a bucket prefix to mirror files into this collection."
            icon={<FolderSync className="size-5" />}
            title="No S3 sources"
          />
        )}
      </section>
      <ConfirmDialog
        confirmLabel="Remove source"
        description={
          deleteFor
            ? `Remove "${deleteFor.root_name}"? This deletes its credentials, mirrored documents, and sync state.`
            : "Remove this source?"
        }
        loading={deletePending}
        onClose={() => setDeleteFor(null)}
        onConfirm={async () => {
          if (!deleteFor) return;
          try {
            await onDelete(deleteFor.id);
            setDeleteFor(null);
          } catch {
            return;
          }
        }}
        open={Boolean(deleteFor)}
        title="Remove source"
      />
    </>
  );
};
