import {
  Badge,
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  cn,
  Empty,
  Page,
  Spinner,
} from "@atelier/ui";
import { getRouteApi, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, RefreshCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { decodeCollectionName } from "@/features/collections/use-collection-name";
import {
  getWorkerAvailability,
  workerOfflineActionMessage,
} from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import {
  useChunks,
  useDeleteDocument,
  useDocument,
  useReprocessDocument,
} from "@/hooks/use-documents";
import { usePlatformStats } from "@/hooks/use-platform";
import { formatBytes, formatNumber, formatRelative } from "@/lib/format";
import type { DocumentProgress, DocumentStatus } from "@/types/bigrag";

const routeApi = getRouteApi("/_dashboard/collections/$name/documents/$docId");

const statusVariant: Record<DocumentStatus | string, "error" | "info" | "success" | "warning"> = {
  complete: "success",
  failed: "error",
  pending: "warning",
  processing: "info",
  ready: "success",
};

const numberDetail = (detail: Record<string, unknown> | undefined, key: string) => {
  const value = detail?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};

const progressDetailText = (progress: DocumentProgress | null | undefined) => {
  const detail = progress?.detail;
  const pagesTotal = numberDetail(detail, "pages_total");
  const pagesDone = numberDetail(detail, "pages_done") ?? numberDetail(detail, "page_end");
  if (pagesTotal && pagesDone) {
    return `Pages ${formatNumber(pagesDone)} of ${formatNumber(pagesTotal)}`;
  }

  const totalBatches = numberDetail(detail, "total_batches");
  const batch = numberDetail(detail, "batch");
  if (totalBatches && batch) {
    return `Batch ${formatNumber(batch)} of ${formatNumber(totalBatches)}`;
  }

  const inserted = numberDetail(detail, "inserted");
  if (inserted) {
    return `${formatNumber(inserted)} vectors inserted`;
  }

  return null;
};

const fallbackProgress = (status: DocumentStatus, chunkCount: number): DocumentProgress => {
  if (status === "ready") {
    return {
      collection_name: "",
      detail: { chunks: chunkCount },
      document_id: "",
      message: `Ready — ${formatNumber(chunkCount)} chunks`,
      progress: 1,
      status: "complete",
      step: "complete",
    };
  }
  if (status === "failed") {
    return {
      collection_name: "",
      detail: {},
      document_id: "",
      message: "Ingestion failed",
      progress: 0,
      status: "failed",
      step: "failed",
    };
  }
  return {
    collection_name: "",
    detail: {},
    document_id: "",
    message: status === "pending" ? "Queued for ingestion" : "Processing document",
    progress: status === "pending" ? 0 : 0.05,
    status,
    step: status === "pending" ? "queued" : "processing",
  };
};

export const DocumentDetail = () => {
  const { name: rawName, docId } = routeApi.useParams();
  const name = decodeCollectionName(rawName);
  const navigate = useNavigate();
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { data: doc, dataUpdatedAt, isPending, streaming } = useDocument(name, docId);
  const { data: chunks, refetch: refetchChunks } = useChunks(name, docId);
  const { data: stats } = usePlatformStats();
  const reprocess = useReprocessDocument(name);
  const remove = useDeleteDocument(name);

  useRefreshChunksWhenReady(doc?.status, refetchChunks);

  if (isPending || !doc) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  const progress = doc.progress ?? fallbackProgress(doc.status, doc.chunk_count);
  const progressPct = Math.max(0, Math.min(100, Math.round(progress.progress * 100)));
  const progressDetail = progressDetailText(progress);
  const progressVariant = statusVariant[progress.status] ?? statusVariant[doc.status] ?? "info";
  const checkedAt = dataUpdatedAt ? new Date(dataUpdatedAt) : null;
  const workerAvailability = getWorkerAvailability(stats);
  const workerOffline = workerAvailability.offline;

  return (
    <Page.Shell>
      <Link
        params={{ name }}
        to="/collections/$name/documents"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Documents
      </Link>

      <WorkerOfflineBanner availability={workerAvailability} />

      <Page.Header
        className="mb-0"
        eyebrow={`${doc.file_type.toUpperCase()} · ${formatBytes(doc.file_size)}`}
        title={doc.filename}
        description={`${doc.chunk_count} chunks · updated ${formatRelative(doc.updated_at)}`}
        actions={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={workerOffline}
              title={workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined}
              onClick={async () => {
                if (workerOffline) {
                  toast.warning(workerOfflineActionMessage(workerAvailability));
                  return;
                }
                try {
                  await reprocess.mutateAsync(docId);
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Failed");
                }
              }}
            >
              <RefreshCcw className="h-4 w-4" />
              Reprocess
            </Button>
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              <Trash2 className="h-4 w-4" />
              Delete
            </Button>
          </div>
        }
      />

      <Card>
        <CardContent className="flex flex-col gap-3 pt-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge dot variant={progressVariant}>
                  {progress.status}
                </Badge>
                <span className="text-sm font-medium capitalize">{progress.step}</span>
              </div>
              <p className="text-sm text-muted-foreground">{progress.message}</p>
            </div>
            {streaming ? (
              <Spinner size="sm" className="mt-1 shrink-0" />
            ) : (
              <span className="shrink-0 text-sm font-medium tabular-nums">{progressPct}%</span>
            )}
          </div>

          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary" style={{ width: `${progressPct}%` }} />
          </div>

          <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>{progressDetail ?? `${progressPct}% complete`}</span>
            <span>Last updated {formatRelative(checkedAt)}</span>
          </div>
        </CardContent>
      </Card>

      {doc.error_message && (
        <Card className="border-destructive">
          <CardContent className="pt-5">
            <div className="flex items-center gap-2 text-sm">
              <Badge variant="error">failed</Badge>
              <span className="font-mono text-xs">{doc.error_message}</span>
            </div>
          </CardContent>
        </Card>
      )}

      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Chunks
          </h2>
          {chunks && chunks.total > chunks.chunks.length && (
            <span className="text-xs text-muted-foreground">
              Showing first {chunks.chunks.length} of {chunks.total} chunks.
            </span>
          )}
        </div>
        {chunks ? (
          chunks.chunks.length === 0 ? (
            <Empty title="No chunks yet" description="Ingestion may still be in progress." />
          ) : (
            <div className="flex flex-col gap-2">
              {chunks.chunks.map((c) => (
                <article
                  id={`chunk-${c.chunk_index}`}
                  key={c.id}
                  className={cn("scroll-mt-24 rounded-xl border border-border bg-card p-4")}
                >
                  <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="neutral">#{c.chunk_index}</Badge>
                    <span className="font-mono">{c.id.slice(0, 8)}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{c.text}</p>
                </article>
              ))}
            </div>
          )
        ) : (
          <Spinner />
        )}
      </div>
      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(docId);
            setDeleteOpen(false);
            navigate({
              to: "/collections/$name/documents",
              params: { name },
              replace: true,
            });
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Delete failed");
          }
        }}
        title="Delete document"
        description={`Delete "${doc.filename}"? This permanently removes its chunks and vectors.`}
        confirmLabel="Delete"
        loading={remove.isPending}
      />
    </Page.Shell>
  );
};

const useRefreshChunksWhenReady = (
  status: DocumentStatus | undefined,
  refetchChunks: ReturnType<typeof useChunks>["refetch"],
) => {
  useEffect(() => {
    if (status === "ready") {
      void refetchChunks();
    }
  }, [status, refetchChunks]);
};
