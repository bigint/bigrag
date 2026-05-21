import { useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, CircleStop, Cloud, Database, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Modal } from "@/components/ui/modal";
import {
  useDeleteVectorMigration,
  useStartVectorMigration,
  useVectorMigrations,
  useVectorStorageOverview,
} from "@/hooks/use-vector-migrations";
import { formatNumber, formatRelative } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { Collection, VectorMigrationJob, VectorMigrationProvider } from "@/types/bigrag";

type VectorMigrationPanelProps = {
  readonly collection?: Collection;
};

type MigrationTarget = {
  readonly collection: string;
  readonly source: VectorMigrationProvider;
  readonly target: VectorMigrationProvider;
};

const PROVIDER_META: Record<VectorMigrationProvider, { label: string; icon: typeof Database }> = {
  qdrant: { label: "Qdrant", icon: Database },
  turbopuffer: { label: "turbopuffer", icon: Cloud },
};

const targetProvider = (provider: VectorMigrationProvider): VectorMigrationProvider =>
  provider === "qdrant" ? "turbopuffer" : "qdrant";

const providerLabel = (provider: VectorMigrationProvider) => PROVIDER_META[provider].label;

const activeStatuses = new Set(["pending", "running", "canceling"]);
const migrationDescription =
  "Move a collection between vector providers. Writes are paused during the job, then old source vectors are deleted after cutover.";

export const VectorMigrationPanel = ({ collection }: VectorMigrationPanelProps) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ArrowRightLeft className="size-4" />
          Vector migration
        </CardTitle>
        <CardDescription>{migrationDescription}</CardDescription>
      </CardHeader>
      <CardContent>
        <VectorMigrationContent collection={collection} />
      </CardContent>
    </Card>
  );
};

export const VectorMigrationModal = ({
  collection,
  onClose,
  open,
}: VectorMigrationPanelProps & {
  readonly onClose: () => void;
  readonly open: boolean;
}) => (
  <Modal
    onClose={onClose}
    open={open}
    size="xl"
    title={collection ? `Migrate ${collection.name}` : "Migrate vector provider"}
  >
    <div className="flex flex-col gap-5">
      <p className="text-sm text-muted-foreground">{migrationDescription}</p>
      <VectorMigrationContent collection={collection} />
    </div>
  </Modal>
);

const VectorMigrationContent = ({ collection }: VectorMigrationPanelProps) => {
  const queryClient = useQueryClient();
  const overview = useVectorStorageOverview();
  const migrations = useVectorMigrations({ collection: collection?.name });
  const startMigration = useStartVectorMigration();
  const deleteMigration = useDeleteVectorMigration();
  const [target, setTarget] = useState<MigrationTarget | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<VectorMigrationJob | null>(null);

  const configuredProviders = overview.data?.configured_providers ?? [];
  const rows = useMemo(() => {
    if (collection) {
      return [
        {
          name: collection.name,
          provider: collection.vector_store_provider,
          documents: collection.document_count,
          chunks: null,
        },
      ];
    }
    return (
      overview.data?.collections.map((item) => ({
        name: item.name,
        provider: item.provider,
        documents: item.documents,
        chunks: item.chunks,
      })) ?? []
    );
  }, [collection, overview.data?.collections]);
  const jobs = migrations.data?.jobs ?? [];
  const activeJob = jobs.find((job) => activeStatuses.has(job.status));
  const completionKey = jobs
    .filter((job) => !activeStatuses.has(job.status))
    .map((job) => `${job.id}:${job.status}:${job.updated_at}`)
    .join("|");

  useEffect(() => {
    if (!completionKey) return;
    queryClient.invalidateQueries({ queryKey: queryKeys.collections.all() });
    queryClient.invalidateQueries({ queryKey: queryKeys.vectorStorageOverview() });
    if (collection) {
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.one({ name: collection.name }),
      });
    }
  }, [collection, completionKey, queryClient]);

  return (
    <>
      <div className="flex flex-col gap-5">
        {rows.length ? (
          <div className="overflow-hidden rounded-md border border-border">
            <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border bg-muted/60 px-4 py-2 text-xs font-semibold text-muted-foreground">
              <span>Collection</span>
              <span>Current</span>
              <span>Action</span>
            </div>
            <div className="divide-y divide-border">
              {rows.map((row) => {
                const nextProvider = targetProvider(row.provider);
                const ready = configuredProviders.includes(nextProvider);
                return (
                  <div
                    key={row.name}
                    className="grid gap-3 px-4 py-3 md:grid-cols-[1fr_auto_auto] md:items-center"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">{row.name}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {formatNumber(row.documents)} documents
                        {row.chunks === null ? "" : ` · ${formatNumber(row.chunks)} chunks`}
                      </div>
                    </div>
                    <ProviderBadge provider={row.provider} />
                    <Button
                      disabled={Boolean(activeJob) || startMigration.isPending || !ready}
                      onClick={() =>
                        setTarget({
                          collection: row.name,
                          source: row.provider,
                          target: nextProvider,
                        })
                      }
                      size="sm"
                      title={
                        ready
                          ? undefined
                          : `${providerLabel(nextProvider)} is not configured in Vector Storage`
                      }
                      variant="secondary"
                    >
                      <ArrowRightLeft className="size-3.5" />
                      Migrate to {providerLabel(nextProvider)}
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <Empty
            icon={<ArrowRightLeft className="size-5" />}
            title="No collections"
            description="Create a collection before starting a vector migration."
            bordered={false}
            className="rounded-md border border-dashed border-border bg-muted/40"
          />
        )}
        <MigrationJobs
          deleting={deleteMigration.isPending}
          jobs={jobs}
          onDelete={setDeleteTarget}
        />
      </div>
      <ConfirmDialog
        open={Boolean(target)}
        onClose={() => setTarget(null)}
        title={target ? `Migrate ${target.collection}?` : "Migrate collection?"}
        description={
          target
            ? `bigRAG will pause writes, copy vectors from ${providerLabel(target.source)} to ${providerLabel(target.target)}, switch the collection, and delete the old ${providerLabel(
                target.source,
              )} vectors.`
            : ""
        }
        confirmLabel="Start migration"
        confirmationLabel={target ? `Type ${target.collection} to start migration` : undefined}
        confirmationText={target?.collection}
        loading={startMigration.isPending}
        onConfirm={async () => {
          if (!target) return;
          await startMigration.mutateAsync({
            collection: target.collection,
            target_provider: target.target,
          });
          setTarget(null);
        }}
      />
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={deleteTarget ? deleteTitle(deleteTarget) : "Delete migration?"}
        description={deleteTarget ? deleteDescription(deleteTarget) : ""}
        confirmLabel={
          deleteTarget && activeStatuses.has(deleteTarget.status) ? "Stop and delete" : "Delete"
        }
        confirmationLabel={
          deleteTarget
            ? `Type ${deleteTarget.collection_name} to ${activeStatuses.has(deleteTarget.status) ? "stop and delete" : "delete"} migration`
            : undefined
        }
        confirmationText={deleteTarget?.collection_name}
        loading={deleteMigration.isPending}
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            await deleteMigration.mutateAsync(deleteTarget);
            setDeleteTarget(null);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed");
          }
        }}
      />
    </>
  );
};

const ProviderBadge = ({ provider }: { readonly provider: VectorMigrationProvider }) => {
  const Icon = PROVIDER_META[provider].icon;
  return (
    <Badge variant="neutral">
      <Icon className="size-3.5" />
      {providerLabel(provider)}
    </Badge>
  );
};

const MigrationJobs = ({
  deleting,
  jobs,
  onDelete,
}: {
  readonly deleting: boolean;
  readonly jobs: VectorMigrationJob[];
  readonly onDelete: (job: VectorMigrationJob) => void;
}) => {
  if (!jobs.length) {
    return (
      <Empty
        icon={<ArrowRightLeft className="size-5" />}
        title="No migration jobs"
        description="Completed and failed migrations appear here."
        bordered={false}
        className="rounded-md border border-dashed border-border bg-muted/40"
      />
    );
  }
  return (
    <div className="overflow-hidden rounded-md border border-border">
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 border-b border-border bg-muted/60 px-4 py-2 text-xs font-semibold text-muted-foreground">
        <span>Migration</span>
        <span>Copied</span>
        <span>Status</span>
        <span>Action</span>
      </div>
      <div className="divide-y divide-border">
        {jobs.map((job) => (
          <MigrationJobRow deleting={deleting} job={job} key={job.id} onDelete={onDelete} />
        ))}
      </div>
    </div>
  );
};

const MigrationJobRow = ({
  deleting,
  job,
  onDelete,
}: {
  readonly deleting: boolean;
  readonly job: VectorMigrationJob;
  readonly onDelete: (job: VectorMigrationJob) => void;
}) => (
  <div className="grid gap-3 px-4 py-3 md:grid-cols-[1fr_auto_auto_auto] md:items-center">
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <div className="truncate text-sm font-semibold">{job.collection_name}</div>
        <span className="text-xs text-muted-foreground">{formatRelative(job.created_at)}</span>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {providerLabel(job.source_provider)} to {providerLabel(job.target_provider)} · {job.phase}
      </div>
      {job.error_message && (
        <div className="mt-1 text-xs text-destructive">{job.error_message}</div>
      )}
      {activeStatuses.has(job.status) && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${Math.max(4, Math.round(job.progress * 100))}%` }}
          />
        </div>
      )}
    </div>
    <div className="text-sm text-muted-foreground">
      {formatNumber(job.copied_points)}
      {job.total_points === null ? "" : ` / ${formatNumber(job.total_points)}`}
    </div>
    <Badge variant={statusVariant(job.status)} dot>
      {job.status}
    </Badge>
    <Button
      disabled={deleting || job.status === "canceling"}
      onClick={() => onDelete(job)}
      size="sm"
      variant={activeStatuses.has(job.status) ? "destructive" : "secondary"}
    >
      {activeStatuses.has(job.status) ? (
        <>
          <CircleStop className="size-3.5" />
          Stop and delete
        </>
      ) : (
        <>
          <Trash2 className="size-3.5" />
          Delete
        </>
      )}
    </Button>
  </div>
);

const statusVariant = (status: VectorMigrationJob["status"]) => {
  if (status === "succeeded") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "primary";
  if (status === "canceling") return "error";
  return "neutral";
};

const deleteTitle = (job: VectorMigrationJob) =>
  activeStatuses.has(job.status) ? "Stop and delete migration?" : "Delete migration?";

const deleteDescription = (job: VectorMigrationJob) =>
  activeStatuses.has(job.status)
    ? `Stop the ${providerLabel(job.source_provider)} to ${providerLabel(job.target_provider)} migration for ${job.collection_name} and remove it from the migration list. If cutover already started, bigRAG will finish cleanup before removing it.`
    : `Delete the ${providerLabel(job.source_provider)} to ${providerLabel(job.target_provider)} migration record for ${job.collection_name}.`;
