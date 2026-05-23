import { useForm, useStore } from "@tanstack/react-form";
import { FolderSync, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import {
  activeS3SyncStatuses,
  clampSyncProgress,
  intervalOptions,
  isActiveS3SyncJob,
  jobStatusVariant,
  sourceStatusVariant,
  syncCountLabel,
  syncProgressForJob,
  syncProgressLabel,
} from "@/features/collections/s3-connector-utils";
import {
  defaultS3SourceFormValues,
  isCloudflareR2Endpoint,
  s3SourcePayload,
  validateS3SourceFormValues,
} from "@/features/collections/s3-source-form-state";
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
import { firstString, submitWith } from "@/lib/form";
import { formatRelative } from "@/lib/format";
import type { ConnectorSyncProgress, S3Source, S3SyncJob } from "@/types/bigrag";

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
          deleteSource={deleteSource}
          jobsBySource={jobsBySource}
          offlineReason={offlineReason}
          onAddSource={() => setAddSourceOpen(true)}
          sources={sources.data?.sources ?? []}
          sourcesPending={sources.isPending}
          syncSource={syncSource}
          updateSource={updateSource}
          workerOffline={workerOffline}
        />
        <aside className="flex min-w-0 flex-col gap-4">
          <SyncMonitor
            isPending={syncJobs.isPending}
            job={activeJob}
            streaming={syncJobs.streaming}
          />
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

const AddS3SourceModal = ({
  isPending,
  onClose,
  onSubmit,
  open,
  workerOffline,
}: {
  isPending: boolean;
  onClose: () => void;
  onSubmit: (value: ReturnType<typeof defaultS3SourceFormValues>) => Promise<void>;
  open: boolean;
  workerOffline: boolean;
}) => (
  <Modal onClose={onClose} open={open} size="lg" title="Add source">
    <S3SourceForm
      isPending={isPending}
      onCancel={onClose}
      onSubmit={onSubmit}
      workerOffline={workerOffline}
    />
  </Modal>
);

const S3SourceForm = ({
  isPending,
  onCancel,
  onSubmit,
  workerOffline,
}: {
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (value: ReturnType<typeof defaultS3SourceFormValues>) => Promise<void> | void;
  workerOffline: boolean;
}) => {
  const form = useForm({
    defaultValues: defaultS3SourceFormValues(),
    validators: {
      onSubmit: ({ value }) => validateS3SourceFormValues(value),
    },
    onSubmit: async ({ value }) => {
      await onSubmit(value);
    },
  });
  const values = useStore(form.store, (state) => state.values);
  const submitError = useStore(form.store, (state) => firstString(state.errors));
  const setEndpointUrl = (endpointUrl: string) => {
    form.setFieldValue("endpointUrl", endpointUrl);
    if (isCloudflareR2Endpoint(endpointUrl)) {
      form.setFieldValue("region", "auto");
    }
  };

  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={submitWith(() => form.handleSubmit())}
    >
      <div className="flex items-center justify-between gap-3 rounded-sm border border-border bg-muted/35 px-3 py-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">S3 / R2 source</div>
          <div className="mt-0.5 text-xs text-muted-foreground">Bucket prefix mirror</div>
        </div>
        <Badge dot variant={workerOffline ? "warning" : "primary"}>
          {workerOffline ? "worker offline" : "ready"}
        </Badge>
      </div>
      {submitError && (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          {submitError}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Bucket"
          onChange={(event) => form.setFieldValue("bucket", event.target.value)}
          placeholder="company-knowledge"
          value={values.bucket}
        />
        <Input
          label="Prefix"
          onChange={(event) => form.setFieldValue("prefix", event.target.value)}
          placeholder="policies/"
          value={values.prefix}
        />
        <Input
          label="Signing region"
          onChange={(event) => form.setFieldValue("region", event.target.value)}
          placeholder="us-east-1 or auto"
          value={values.region}
        />
        <Input
          label="Endpoint URL"
          onChange={(event) => setEndpointUrl(event.target.value)}
          placeholder="https://account-id.r2.cloudflarestorage.com"
          value={values.endpointUrl}
        />
        <Input
          label="Access key ID"
          onChange={(event) => form.setFieldValue("accessKeyId", event.target.value)}
          value={values.accessKeyId}
        />
        <Input
          label="Secret access key"
          onChange={(event) => form.setFieldValue("secretAccessKey", event.target.value)}
          type="password"
          value={values.secretAccessKey}
        />
        <Input
          label="Session token"
          onChange={(event) => form.setFieldValue("sessionToken", event.target.value)}
          type="password"
          value={values.sessionToken}
        />
        <Select
          label="Sync interval"
          onChange={(value) => form.setFieldValue("syncIntervalHours", value)}
          options={intervalOptions}
          value={values.syncIntervalHours}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-background p-3">
        <div className="flex flex-wrap items-center gap-5">
          <Switch
            checked={values.scheduleEnabled}
            label="Scheduled"
            onCheckedChange={(checked) => form.setFieldValue("scheduleEnabled", checked)}
          />
          <Switch
            checked={values.forcePathStyle}
            label="Path style"
            onCheckedChange={(checked) => form.setFieldValue("forcePathStyle", checked)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onCancel} type="button" variant="outline">
            Cancel
          </Button>
          <Button disabled={isPending || workerOffline} type="submit">
            {isPending ? <Spinner /> : <FolderSync className="size-4" />}
            Add source
          </Button>
        </div>
      </div>
    </form>
  );
};

const SyncMonitor = ({
  isPending,
  job,
  streaming,
}: {
  isPending: boolean;
  job: S3SyncJob | undefined;
  streaming: boolean;
}) => (
  <section className="min-w-0 overflow-hidden rounded-sm border border-border bg-card">
    <div className="flex items-center justify-between border-border border-b px-4 py-3">
      <h3 className="text-sm font-semibold">Sync monitor</h3>
      {streaming && <Badge variant="primary">live</Badge>}
    </div>
    {isPending ? (
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
          <div className="text-sm font-semibold">{syncProgressLabel(progress)}</div>
          <div className="mt-1 text-xs text-muted-foreground">{syncCountLabel(progress)}</div>
        </div>
        <Badge dot variant={jobStatusVariant[job.status]}>
          {job.status}
        </Badge>
      </div>
      <ProgressBar progress={progress} />
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

const ProgressBar = ({ progress }: { progress: ConnectorSyncProgress }) => (
  <div className="h-2 overflow-hidden rounded-full bg-muted">
    <div
      className="h-full rounded-full bg-primary"
      style={{ width: `${clampSyncProgress(progress.progress_percent)}%` }}
    />
  </div>
);

const SyncCount = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-sm border border-border bg-background px-2 py-2">
    <div className="text-muted-foreground">{label}</div>
    <div className="mt-1 font-semibold">{value.toLocaleString()}</div>
  </div>
);

const SourcesPanel = ({
  addSourceDisabled,
  deleteSource,
  jobsBySource,
  offlineReason,
  onAddSource,
  sources,
  sourcesPending,
  syncSource,
  updateSource,
  workerOffline,
}: {
  addSourceDisabled: boolean;
  deleteSource: ReturnType<typeof useDeleteS3Source>;
  jobsBySource: Map<string, S3SyncJob>;
  offlineReason?: string;
  onAddSource: () => void;
  sources: S3Source[];
  sourcesPending: boolean;
  syncSource: ReturnType<typeof useSyncS3Source>;
  updateSource: ReturnType<typeof useUpdateS3Source>;
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
                isDeleting={deleteSource.isPending}
                job={jobsBySource.get(source.id)}
                key={source.id}
                offlineReason={offlineReason}
                onDelete={() => setDeleteFor(source)}
                source={source}
                syncSource={syncSource}
                updateSource={updateSource}
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
        loading={deleteSource.isPending}
        onClose={() => setDeleteFor(null)}
        onConfirm={async () => {
          if (!deleteFor) return;
          try {
            await deleteSource.mutateAsync(deleteFor.id);
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

const SourceRow = ({
  isDeleting,
  job,
  offlineReason,
  onDelete,
  source,
  syncSource,
  updateSource,
  workerOffline,
}: {
  isDeleting: boolean;
  job: S3SyncJob | undefined;
  offlineReason?: string;
  onDelete: () => void;
  source: S3Source;
  syncSource: ReturnType<typeof useSyncS3Source>;
  updateSource: ReturnType<typeof useUpdateS3Source>;
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
              disabled={syncSource.isPending || isSyncing || workerOffline}
              onClick={() => syncSource.mutate(source.id)}
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
              {syncProgressLabel(progress)}
            </span>
            <span className="font-semibold">{clampSyncProgress(progress.progress_percent)}%</span>
          </div>
          <div className="mt-2">
            <ProgressBar progress={progress} />
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
