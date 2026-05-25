import { useMemo, useState } from "react";
import { AddS3SourceModal } from "@/features/collections/s3/add-s3-source-modal";
import { SourcesPanel } from "@/features/collections/s3/sources-panel";
import { SyncMonitor } from "@/features/collections/s3/sync-monitor";
import { activeS3SyncStatuses } from "@/features/collections/s3-connector-utils";
import { s3SourcePayload } from "@/features/collections/s3-source-form-state";
import {
  getWorkerAvailability,
  workerOfflineActionMessage,
} from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { usePlatformStats } from "@/hooks/use-platform";
import {
  useCreateS3Source,
  useDeleteS3Source,
  useS3Sources,
  useS3SyncJobs,
  useSyncS3Source,
  useUpdateS3Source,
} from "@/hooks/use-s3-connector";
import type { S3SyncJob } from "@/types/bigrag";

export const S3ConnectorPanel = ({ collection }: { collection: string }) => {
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const sources = useS3Sources(collection);
  const syncJobs = useS3SyncJobs({ collection, limit: 20 });
  const createSource = useCreateS3Source(collection);
  const syncSource = useSyncS3Source(collection);
  const updateSource = useUpdateS3Source(collection);
  const deleteSource = useDeleteS3Source(collection);
  const { data: stats } = usePlatformStats();
  const workerAvailability = getWorkerAvailability(stats);
  const workerOffline = workerAvailability.offline;
  const offlineReason = workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined;
  const jobsBySource = useMemo(() => {
    const map = new Map<string, S3SyncJob>();
    for (const job of syncJobs.data?.jobs ?? []) {
      if (job.source_id && !map.has(job.source_id)) map.set(job.source_id, job);
    }
    return map;
  }, [syncJobs.data?.jobs]);
  const activeJob = useMemo(
    () =>
      syncJobs.data?.jobs.find((job) => activeS3SyncStatuses.has(job.status)) ??
      syncJobs.data?.jobs[0],
    [syncJobs.data?.jobs],
  );
  const addSourceDisabled = createSource.isPending || workerOffline;

  return (
    <div className="flex flex-col gap-4">
      <WorkerOfflineBanner availability={workerAvailability} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <SourcesPanel
          addSourceDisabled={addSourceDisabled}
          deletePending={deleteSource.isPending}
          jobsBySource={jobsBySource}
          offlineReason={offlineReason}
          onAddSource={() => setAddSourceOpen(true)}
          onChangeInterval={(sourceId, hours) =>
            updateSource.mutate({ body: { sync_interval_hours: hours }, sourceId })
          }
          onDelete={async (sourceId) => {
            await deleteSource.mutateAsync(sourceId);
          }}
          onSync={(sourceId) => syncSource.mutate(sourceId)}
          onToggleSchedule={(sourceId, enabled) =>
            updateSource.mutate({ body: { schedule_enabled: enabled }, sourceId })
          }
          sources={sources.data?.sources ?? []}
          sourcesPending={sources.isPending}
          syncPending={syncSource.isPending}
          updatePending={updateSource.isPending}
          workerOffline={workerOffline}
        />
        <aside className="flex min-w-0 flex-col gap-4">
          <SyncMonitor isPending={syncJobs.isPending} job={activeJob} />
        </aside>
      </div>
      {addSourceOpen && (
        <AddS3SourceModal
          isPending={createSource.isPending}
          onClose={() => setAddSourceOpen(false)}
          onSubmit={async (value) => {
            try {
              await createSource.mutateAsync(s3SourcePayload(value));
              setAddSourceOpen(false);
            } catch {
              return;
            }
          }}
          open={addSourceOpen}
          workerOffline={workerOffline}
        />
      )}
    </div>
  );
};
