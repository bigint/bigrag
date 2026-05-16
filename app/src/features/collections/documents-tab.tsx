import { Link } from "@tanstack/react-router";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileText,
  FolderOpen,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useUploadSessionStore } from "@/features/collections/upload-session-store";
import {
  getWorkerAvailability,
  workerOfflineActionMessage,
} from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { useCollection } from "@/hooks/use-collections";
import {
  type DocumentListFilters,
  type DocumentListOrder,
  type DocumentListSort,
  useBatchDeleteDocuments,
  useCancelUploadSession,
  useDeleteDocument,
  useDocuments,
  useUploadSession,
  useUploadSessionDocuments,
} from "@/hooks/use-documents";
import { usePlatformStats } from "@/hooks/use-platform";
import { cn } from "@/lib/cn";
import { acceptAttribute, filterBlockedFiles, getAllowedFileTypes } from "@/lib/file-types";
import { formatBytes, formatRelative } from "@/lib/format";
import type { DocumentStatus, UploadSession } from "@/types/bigrag";

const statusVariant: Record<DocumentStatus, "success" | "warning" | "info" | "error"> = {
  ready: "success",
  processing: "info",
  pending: "warning",
  failed: "error",
};

const pageSize = 25;
const statusOptions = [
  { value: "all", label: "All statuses" },
  { value: "ready", label: "Ready" },
  { value: "processing", label: "Processing" },
  { value: "pending", label: "Pending" },
  { value: "failed", label: "Failed" },
];
const sortOptions: { value: DocumentListSort; label: string }[] = [
  { value: "created_at", label: "Created" },
  { value: "updated_at", label: "Updated" },
  { value: "filename", label: "Filename" },
  { value: "file_size", label: "Size" },
  { value: "chunk_count", label: "Chunks" },
  { value: "status", label: "Status" },
];
const orderOptions: { value: DocumentListOrder; label: string }[] = [
  { value: "desc", label: "Desc" },
  { value: "asc", label: "Asc" },
];

type DocumentsTabFilters = {
  order: DocumentListOrder;
  page: number;
  q: string;
  sort: DocumentListSort;
  status: string;
};

type DocumentsTabProps = {
  filters?: DocumentsTabFilters;
  name: string;
  onFiltersChange?: (filters: Partial<DocumentsTabFilters>) => void;
};

export const DocumentsTab = ({ filters, name, onFiltersChange }: DocumentsTabProps) => {
  const activeFilters = filters ?? {
    order: "desc",
    page: 1,
    q: "",
    sort: "created_at",
    status: "",
  };
  const activeSessionId = useUploadSessionStore((state) => state.activeSessionIds[name] ?? null);
  const clearActiveSessionId = useUploadSessionStore((state) => state.clearActiveSessionId);
  const setActiveSessionId = useUploadSessionStore((state) => state.setActiveSessionId);

  const { data: collection } = useCollection(name);
  const [qDraft, setQDraft] = useState(activeFilters.q);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const offset = (activeFilters.page - 1) * pageSize;
  const documentFilters: DocumentListFilters = {
    limit: pageSize,
    offset,
    order: activeFilters.order,
    q: activeFilters.q,
    sort: activeFilters.sort,
    status: activeFilters.status,
  };
  const { data, error, isError, isPending, refetch, realtimeUnavailable } = useDocuments(
    name,
    documentFilters,
  );
  const { data: stats } = usePlatformStats();
  const uploadSession = useUploadSession(name, activeSessionId);
  const upload = useUploadSessionDocuments(name, {
    onSessionStart: (session) => setActiveSessionId(name, session.id),
  });
  const cancelSession = useCancelUploadSession(name);
  const remove = useDeleteDocument(name);
  const batchRemove = useBatchDeleteDocuments(name);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [deleteDoc, setDeleteDoc] = useState<{ id: string; filename: string } | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const allowed = getAllowedFileTypes(collection?.metadata);
  const accept = acceptAttribute(allowed);
  const workerAvailability = getWorkerAvailability(stats);
  const workerOffline = workerAvailability.offline;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;
  const pageDocuments = data?.documents ?? [];
  const selectedVisibleCount = pageDocuments.filter((doc) => selected.has(doc.id)).length;
  const allVisibleSelected =
    pageDocuments.length > 0 && selectedVisibleCount === pageDocuments.length;
  const selectedDocuments = pageDocuments.filter((doc) => selected.has(doc.id));
  const bulkConfirmationText = `DELETE ${selectedDocuments.length}`;

  useEffect(() => {
    setQDraft(activeFilters.q);
  }, [activeFilters.q]);

  useEffect(() => {
    if (uploadSession.isError && getErrorStatus(uploadSession.error) === 404) {
      clearActiveSessionId(name);
    }
  }, [clearActiveSessionId, name, uploadSession.error, uploadSession.isError]);

  useEffect(() => {
    setSelected((current) => {
      const visible = new Set(pageDocuments.map((doc) => doc.id));
      const next = new Set([...current].filter((id) => visible.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [pageDocuments]);

  const updateFilters = (next: Partial<DocumentsTabFilters>) => {
    onFiltersChange?.({ ...next, page: next.page ?? 1 });
  };

  const toggleVisibleSelection = () => {
    setSelected((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        for (const doc of pageDocuments) next.delete(doc.id);
      } else {
        for (const doc of pageDocuments) next.add(doc.id);
      }
      return next;
    });
  };

  const toggleDocumentSelection = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const onFiles = useCallback(
    async (files: FileList | File[]) => {
      if (workerOffline) {
        toast.warning(workerOfflineActionMessage(workerAvailability));
        return;
      }
      const arr = Array.from(files);
      if (!arr.length) return;
      const { accepted, rejected } = filterBlockedFiles(arr, allowed);
      if (rejected.length) {
        toast.warning(
          `${rejected.length} file${rejected.length === 1 ? "" : "s"} skipped — not allowed in this collection.`,
        );
      }
      if (accepted.length) {
        const duplicateCount = countDuplicateNames(accepted);
        if (duplicateCount) {
          toast.info(
            `${duplicateCount} duplicate filename${duplicateCount === 1 ? "" : "s"} selected`,
          );
        }
        const totalSize = accepted.reduce((sum, file) => sum + file.size, 0);
        toast.info(
          `${accepted.length} file${accepted.length === 1 ? "" : "s"} selected (${formatBytes(totalSize)})`,
        );
        const res = await upload.mutateAsync(accepted);
        setActiveSessionId(name, res.session.id);
        if (fileInput.current) fileInput.current.value = "";
        if (folderInput.current) folderInput.current.value = "";
      }
    },
    [upload, allowed, name, setActiveSessionId, workerAvailability, workerOffline],
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
  };

  const acceptedDescription = allowed.length
    ? `Only ${allowed.map((t) => `.${t}`).join(", ")} allowed in this collection.`
    : "PDF, DOCX, PPTX, MD, HTML, TXT, images — ingested automatically.";

  return (
    <div className="flex flex-col gap-4">
      <WorkerOfflineBanner availability={workerAvailability} />
      <fieldset
        aria-label="Document upload"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed px-6 py-8 text-sm",
          "border-border bg-card hover:border-primary hover:bg-accent/50",
          dragging && !workerOffline && "border-primary bg-accent",
          upload.isPending && "pointer-events-none opacity-60",
          workerOffline && "bg-muted/45 hover:border-border hover:bg-muted/45",
        )}
      >
        <div className="flex items-center gap-3">
          <Upload className="size-5 text-muted-foreground" />
          <div className="flex flex-col items-start gap-0.5">
            <span className="font-medium">
              {upload.isPending
                ? "Uploading…"
                : workerOffline
                  ? "Worker offline"
                  : "Drop files here"}
            </span>
            <span className="text-xs text-muted-foreground">{acceptedDescription}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button
            disabled={upload.isPending || workerOffline}
            onClick={() => fileInput.current?.click()}
            size="sm"
            title={workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined}
          >
            <Upload className="size-4" />
            Files
          </Button>
          <Button
            disabled={upload.isPending || workerOffline}
            onClick={() => folderInput.current?.click()}
            size="sm"
            title={workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined}
            variant="secondary"
          >
            <FolderOpen className="size-4" />
            Folder
          </Button>
        </div>
        <input
          ref={fileInput}
          id="doc-upload"
          type="file"
          multiple
          className="sr-only"
          accept={accept}
          disabled={workerOffline}
          onChange={(e) => e.target.files && onFiles(e.target.files)}
        />
        <input
          ref={folderInput}
          type="file"
          multiple
          className="sr-only"
          accept={accept}
          disabled={workerOffline}
          onChange={(e) => e.target.files && onFiles(e.target.files)}
          {...{ webkitdirectory: "", directory: "" }}
        />
      </fieldset>

      {activeSessionId && uploadSession.data && (
        <UploadSessionProgressPanel
          loadingCancel={cancelSession.isPending}
          onCancel={() => cancelSession.mutate(activeSessionId)}
          onDismiss={() => clearActiveSessionId(name)}
          session={uploadSession.data}
          streaming={uploadSession.streaming}
        />
      )}

      {activeSessionId && uploadSession.isError && getErrorStatus(uploadSession.error) !== 404 && (
        <Card className="overflow-hidden rounded-xl border-destructive/25">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex min-w-0 items-center gap-3">
              <CircleAlert className="size-4 text-destructive" />
              <span className="text-sm text-muted-foreground">
                {uploadSession.error instanceof Error
                  ? uploadSession.error.message
                  : "Upload session unavailable"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="secondary" onClick={() => uploadSession.refetch()}>
                Retry
              </Button>
              <Button size="sm" variant="ghost" onClick={() => clearActiveSessionId(name)}>
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeSessionId && !uploadSession.data && uploadSession.isPending && (
        <Card className="overflow-hidden rounded-xl">
          <CardContent className="flex items-center gap-3 p-4">
            <Spinner size="sm" />
            <span className="text-sm text-muted-foreground">Loading upload session…</span>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-xl">
        <CardContent className="flex flex-col gap-3 p-4">
          <form
            className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_160px_140px_120px_auto]"
            onSubmit={(event) => {
              event.preventDefault();
              updateFilters({ q: qDraft.trim() });
            }}
          >
            <Input
              aria-label="Search documents"
              maxLength={200}
              onChange={(event) => setQDraft(event.target.value)}
              placeholder="Search filename, type, id, or error"
              trailing={<Search className="size-4" />}
              value={qDraft}
            />
            <Select
              aria-label="Status"
              onChange={(value) => updateFilters({ status: value === "all" ? "" : value })}
              options={statusOptions}
              value={activeFilters.status || "all"}
            />
            <Select
              aria-label="Sort"
              onChange={(value) => updateFilters({ sort: value as DocumentListSort })}
              options={sortOptions}
              value={activeFilters.sort}
            />
            <Select
              aria-label="Order"
              onChange={(value) => updateFilters({ order: value as DocumentListOrder })}
              options={orderOptions}
              value={activeFilters.order}
            />
            <div className="flex items-center gap-2">
              <Button type="submit">Apply</Button>
              {(activeFilters.q || activeFilters.status) && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setQDraft("");
                    updateFilters({ q: "", status: "" });
                  }}
                >
                  Clear
                </Button>
              )}
            </div>
          </form>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>
              {data
                ? `${data.total.toLocaleString()} matching document${data.total === 1 ? "" : "s"}`
                : "Documents"}
              {realtimeUnavailable ? " · realtime unavailable, polling" : ""}
            </span>
            {selected.size > 0 && (
              <div className="flex items-center gap-2">
                <span>{selected.size} selected</span>
                <Button size="sm" variant="secondary" onClick={() => setSelected(new Set())}>
                  Clear selection
                </Button>
                <Button size="sm" variant="destructive" onClick={() => setBulkDeleteOpen(true)}>
                  <Trash2 className="size-4" />
                  Delete selected
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : isError ? (
        <Card className="rounded-xl border-destructive/25">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h3 className="text-sm font-semibold">Documents unavailable</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {error instanceof Error ? error.message : "Document list could not load."}
              </p>
            </div>
            <Button variant="secondary" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : data?.documents.length === 0 ? (
        <Empty
          icon={<FileText className="size-6" />}
          title={
            activeFilters.q || activeFilters.status ? "No matching documents" : "No documents yet"
          }
          description={
            activeFilters.q || activeFilters.status
              ? "Adjust filters to see more documents."
              : "Upload files above and they will appear here as they ingest."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="border-b border-border">
            <div className="grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              <input
                aria-label="Select visible documents"
                checked={allVisibleSelected}
                className="size-4 rounded border-border"
                onChange={toggleVisibleSelection}
                type="checkbox"
              />
              <span>Filename</span>
              <span className="text-right">Size</span>
              <span className="text-right">Chunks</span>
              <span className="text-right">Updated</span>
              <span className="w-6" />
            </div>
            {data && data.total > data.documents.length && (
              <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
                Showing {offset + 1}-{Math.min(offset + data.documents.length, data.total)} of{" "}
                {data.total} documents.
              </div>
            )}
          </div>
          <ul className="divide-y divide-border">
            {data?.documents.map((d) => (
              <li
                key={d.id}
                className="group grid grid-cols-[auto_1fr_auto_auto_auto_auto] items-center gap-4 px-4 py-3 hover:bg-muted"
              >
                <input
                  aria-label={`Select ${d.filename}`}
                  checked={selected.has(d.id)}
                  className="size-4 rounded border-border"
                  onChange={() => toggleDocumentSelection(d.id)}
                  type="checkbox"
                />
                <Link
                  params={{ docId: d.id, name }}
                  to="/collections/$name/documents/$docId"
                  className="flex min-w-0 items-center gap-3"
                >
                  <FileType type={d.file_type} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{d.filename}</div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <Badge dot variant={statusVariant[d.status]}>
                        {d.status}
                      </Badge>
                      {d.error_message && (
                        <span className="truncate text-xs text-destructive">{d.error_message}</span>
                      )}
                    </div>
                  </div>
                </Link>
                <span className="text-right text-sm tabular-nums text-muted-foreground">
                  {formatBytes(d.file_size)}
                </span>
                <span className="text-right text-sm tabular-nums text-muted-foreground">
                  {d.chunk_count}
                </span>
                <span className="text-right text-sm text-muted-foreground">
                  {formatRelative(d.updated_at)}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete"
                  onClick={(e) => {
                    e.preventDefault();
                    setDeleteDoc({ id: d.id, filename: d.filename });
                  }}
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data && totalPages > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button
            disabled={activeFilters.page <= 1}
            size="sm"
            variant="secondary"
            onClick={() => onFiltersChange?.({ page: activeFilters.page - 1 })}
          >
            <ChevronLeft className="size-4" />
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {activeFilters.page} of {totalPages}
          </span>
          <Button
            disabled={activeFilters.page >= totalPages}
            size="sm"
            variant="secondary"
            onClick={() => onFiltersChange?.({ page: activeFilters.page + 1 })}
          >
            Next
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}

      <ConfirmDialog
        confirmLabel="Delete"
        description={
          deleteDoc
            ? `Delete "${deleteDoc.filename}"? This removes the document and its vectors.`
            : ""
        }
        loading={remove.isPending}
        onClose={() => setDeleteDoc(null)}
        onConfirm={async () => {
          if (!deleteDoc) return;
          try {
            await remove.mutateAsync(deleteDoc.id);
            setDeleteDoc(null);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Delete failed");
          }
        }}
        open={!!deleteDoc}
        title="Delete document"
      />
      <ConfirmDialog
        confirmLabel="Delete selected"
        confirmationLabel={`Type ${bulkConfirmationText} to confirm`}
        confirmationText={bulkConfirmationText}
        description={`This permanently removes ${selectedDocuments.length} document${selectedDocuments.length === 1 ? "" : "s"} and their vectors.`}
        loading={batchRemove.isPending}
        onClose={() => setBulkDeleteOpen(false)}
        onConfirm={async () => {
          const ids = selectedDocuments.map((doc) => doc.id);
          if (!ids.length) return;
          await batchRemove.mutateAsync(ids);
          setSelected(new Set());
          setBulkDeleteOpen(false);
        }}
        open={bulkDeleteOpen}
        title="Delete selected documents"
      />
    </div>
  );
};

const FileType = ({ type }: { type: string }) => (
  <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
    {type.slice(0, 4) || "?"}
  </div>
);

const fileDisplayName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const countDuplicateNames = (files: File[]) => {
  const seen = new Set<string>();
  let count = 0;
  for (const file of files) {
    const name = fileDisplayName(file);
    if (seen.has(name)) count += 1;
    seen.add(name);
  }
  return count;
};

const getErrorStatus = (error: unknown) => {
  if (!error || typeof error !== "object" || !("status" in error)) return undefined;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : undefined;
};

const sessionVariant = (
  status: UploadSession["status"],
): "success" | "warning" | "info" | "error" | "neutral" => {
  if (status === "complete") return "success";
  if (status === "failed") return "error";
  if (status === "canceled") return "warning";
  if (status === "ingesting" || status === "uploading") return "info";
  return "neutral";
};

const itemVariant = (
  status: UploadSession["recent_items"][number]["status"],
): "success" | "warning" | "info" | "error" | "neutral" => {
  if (status === "complete") return "success";
  if (status === "failed") return "error";
  if (status === "canceled") return "warning";
  if (status === "ingesting") return "info";
  return "neutral";
};

const sessionProgress = (session: UploadSession) => {
  if (!session.total_files) return 0;
  const weighted =
    session.completed_files +
    session.failed_files +
    session.canceled_files +
    session.processing_files * 0.6 +
    session.queued_files * 0.25;
  return Math.round(Math.max(0, Math.min(1, weighted / session.total_files)) * 100);
};

const UploadSessionProgressPanel = ({
  loadingCancel,
  onCancel,
  onDismiss,
  session,
  streaming,
}: {
  loadingCancel: boolean;
  onCancel: () => void;
  onDismiss: () => void;
  session: UploadSession;
  streaming: boolean;
}) => {
  const progressPct = sessionProgress(session);
  const remaining = Math.max(session.total_files - session.uploaded_files, 0);
  const terminal =
    session.status === "complete" || session.status === "failed" || session.status === "canceled";
  const active = session.recent_items.find(
    (item) => item.status === "queued" || item.status === "ingesting",
  );
  const failedItems = session.recent_items.filter((item) => item.status === "failed");
  const statusLabel =
    session.status === "complete" && session.failed_files
      ? "finished with failures"
      : session.status;

  return (
    <Card className="overflow-hidden rounded-xl">
      <CardContent className="flex flex-col gap-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">Upload session</span>
              <Badge dot variant={sessionVariant(session.status)}>
                {statusLabel}
              </Badge>
            </div>
            <span className="text-xs text-muted-foreground">
              {session.uploaded_files} of {session.total_files} file
              {session.total_files === 1 ? "" : "s"} received
            </span>
          </div>
          <div className="flex items-center gap-1">
            {!terminal && (
              <Button
                aria-label="Cancel upload session"
                disabled={loadingCancel}
                onClick={onCancel}
                size="sm"
                variant="secondary"
              >
                Cancel
              </Button>
            )}
            <Button
              aria-label="Dismiss upload session"
              onClick={onDismiss}
              size="icon"
              variant="ghost"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <SessionMetric
            icon={<CheckCircle2 className="size-3.5" />}
            label="Completed"
            value={session.completed_files}
          />
          <SessionMetric
            label="Ingesting"
            value={session.processing_files + session.queued_files}
          />
          <SessionMetric label="Uploading" value={remaining} />
          <SessionMetric
            icon={<CircleAlert className="size-3.5" />}
            label="Failed"
            value={session.failed_files}
            variant={session.failed_files ? "error" : "neutral"}
          />
        </div>

        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-primary" style={{ width: `${progressPct}%` }} />
        </div>

        {active && (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/60 p-3">
            <FileType type={active.file_type} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{active.filename}</div>
              <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
                <Badge dot variant={itemVariant(active.status)}>
                  {active.status}
                </Badge>
                <span className="truncate text-xs text-muted-foreground">
                  {formatBytes(active.file_size)}
                </span>
              </div>
            </div>
            {!terminal && streaming && <Spinner size="sm" className="shrink-0" />}
          </div>
        )}

        {failedItems.length > 0 && (
          <div className="flex flex-col gap-1 border-border border-t pt-3">
            {failedItems.slice(0, 2).map((item) => (
              <div key={item.document_id} className="flex min-w-0 items-center gap-2 text-xs">
                <Badge variant="error">failed</Badge>
                <span className="truncate font-medium">{item.filename}</span>
                <span className="truncate text-destructive">
                  {item.error_message ?? "Upload failed"}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const SessionMetric = ({
  icon,
  label,
  value,
  variant = "neutral",
}: {
  icon?: React.ReactNode;
  label: string;
  value: number;
  variant?: "neutral" | "error";
}) => (
  <div
    className={cn(
      "flex min-w-0 flex-col gap-1 rounded-lg border border-border bg-muted/50 px-3 py-2",
      variant === "error" && "border-destructive/30 bg-destructive/5 text-destructive",
    )}
  >
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      {icon}
      {label}
    </span>
    <span className="text-lg font-semibold tabular-nums leading-none">{value}</span>
  </div>
);
