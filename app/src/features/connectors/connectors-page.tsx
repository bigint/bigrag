import { useNavigate } from "@tanstack/react-router";
import { Database, ExternalLink, FolderSync, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Page } from "@/components/ui/page";
import { QueryError } from "@/components/ui/query-error";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import {
  isActiveS3SyncJob,
  sourceStatusVariant,
  syncProgressForJob,
  syncStatusLabel,
} from "@/features/collections/s3-connector-utils";
import {
  connectorCollectionHref,
  connectorProviderById,
  connectorStatus,
  defaultConnectorProvider,
} from "@/features/connectors/connector-catalog";
import {
  useDeleteS3Source,
  useS3Sources,
  useS3SyncJobs,
  useSyncS3Source,
} from "@/hooks/use-s3-connector";
import { formatRelative } from "@/lib/format";
import type { S3Source, S3SyncJob } from "@/types/bigrag";

export const ConnectorsPage = () => {
  const provider = connectorProviderById(defaultConnectorProvider.id);
  const sources = useS3Sources();
  const syncJobs = useS3SyncJobs({ limit: 50 });
  const syncSource = useSyncS3Source();
  const deleteSource = useDeleteS3Source();
  const navigate = useNavigate();
  const [deleteFor, setDeleteFor] = useState<S3Source | null>(null);
  const status = connectorStatus(sources.data?.total ?? 0);
  const ProviderIcon = provider.icon;
  const jobsBySource = new Map<string, S3SyncJob>();
  for (const job of syncJobs.data?.jobs ?? []) {
    if (job.source_id && !jobsBySource.has(job.source_id)) jobsBySource.set(job.source_id, job);
  }

  return (
    <Page.Shell>
      <Page.Header
        className="mb-0"
        description="Manage object-storage sources that mirror bucket prefixes into collections."
        title="Connectors"
      />

      <section className="overflow-hidden rounded-md border border-border bg-card">
        <div className="flex flex-wrap items-start justify-between gap-3 border-border border-b bg-muted/35 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-md border border-border bg-background">
              <ProviderIcon className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold">{provider.label}</h2>
                <Badge variant="neutral">{provider.category}</Badge>
              </div>
              <p className="mt-0.5 text-sm text-muted-foreground">{status.detail}</p>
            </div>
          </div>
          <Badge dot variant={status.variant}>
            {status.label}
          </Badge>
        </div>

        {sources.isError ? (
          <QueryError
            className="m-4"
            error={sources.error}
            onRetry={() => sources.refetch()}
            title="Connector sources could not load"
          />
        ) : syncJobs.isError ? (
          <QueryError
            className="m-4"
            error={syncJobs.error}
            onRetry={() => syncJobs.refetch()}
            title="Connector sync jobs could not load"
          />
        ) : sources.isPending ? (
          <div className="flex h-48 items-center justify-center">
            <Spinner />
          </div>
        ) : sources.data?.sources.length ? (
          <ul className="divide-y divide-border">
            {sources.data.sources.map((source) => (
              <SourceRow
                isDeleting={deleteSource.isPending}
                isSyncing={syncSource.isPending}
                job={jobsBySource.get(source.id)}
                key={source.id}
                navigate={navigate}
                onDelete={() => setDeleteFor(source)}
                onSync={(sourceId) => syncSource.mutate(sourceId)}
                source={source}
              />
            ))}
          </ul>
        ) : (
          <Empty
            bordered={false}
            className="py-16"
            description="Add a source from a collection connector tab."
            icon={<Database className="size-5" />}
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
    </Page.Shell>
  );
};

const SourceRow = ({
  isDeleting,
  isSyncing,
  job,
  navigate,
  onDelete,
  onSync,
  source,
}: {
  isDeleting: boolean;
  isSyncing: boolean;
  job: S3SyncJob | undefined;
  navigate: ReturnType<typeof useNavigate>;
  onDelete: () => void;
  onSync: (sourceId: string) => void;
  source: S3Source;
}) => {
  const active = source.status === "syncing" || isActiveS3SyncJob(job);
  const progress = job ? syncProgressForJob(job) : undefined;
  const href = connectorCollectionHref(source.collection_name, defaultConnectorProvider);
  return (
    <li className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_minmax(180px,280px)_auto] lg:items-center">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <FolderSync className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate text-sm font-semibold">{source.root_name}</span>
          <Badge dot variant={sourceStatusVariant[source.status]}>
            {source.status}
          </Badge>
        </div>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{source.collection_name}</span>
          <span>{source.region}</span>
          {source.last_sync_at && <span>last {formatRelative(source.last_sync_at)}</span>}
        </div>
      </div>
      <div className="min-w-0 truncate text-xs text-muted-foreground">
        {progress ? syncStatusLabel(progress) : "No sync job yet"}
      </div>
      <div className="flex items-center gap-1">
        <Tooltip content="Open collection source">
          <Button
            aria-label="Open collection source"
            onClick={() => {
              navigate({ to: href });
            }}
            size="icon"
            variant="outline"
          >
            <ExternalLink className="size-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Sync now">
          <Button
            aria-label="Sync source"
            disabled={isSyncing || active}
            onClick={() => onSync(source.id)}
            size="icon"
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
    </li>
  );
};
