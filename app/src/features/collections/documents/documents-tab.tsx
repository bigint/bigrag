import { CircleAlert, FolderOpen, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { DeleteDocumentDialogs } from "@/features/collections/documents/delete-document-dialogs";
import { DocumentsEmptyState } from "@/features/collections/documents/documents-empty-state";
import { DocumentsTable } from "@/features/collections/documents/documents-table";
import { DocumentsToolbar } from "@/features/collections/documents/documents-toolbar";
import { UploadSessionPanel } from "@/features/collections/documents/upload-session-panel";
import { useDocumentUpload } from "@/features/collections/documents/use-document-upload";
import { useDocumentsTabState } from "@/features/collections/documents/use-documents-tab-state";
import { useUploadSessionStore } from "@/features/collections/upload-session-store";
import { workerOfflineActionMessage } from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { useCollection } from "@/hooks/use-collections";
import {
  type DocumentListFilters,
  type DocumentListOrder,
  type DocumentListSort,
  useBatchDeleteDocuments,
  useCancelUploadSession,
  useDeleteDocument,
  useInfiniteDocuments,
  useUploadSession,
} from "@/hooks/use-documents";
import { useInfiniteScroll } from "@/hooks/use-infinite-scroll";
import { cn } from "@/lib/cn";
import { acceptAttribute, getAllowedFileTypes } from "@/lib/file-types";
import type { UploadSession } from "@/types/bigrag";

const pageSize = 25;

const shouldDismissUploadSession = (session: UploadSession) =>
  (session.status === "complete" || session.status === "failed" || session.status === "canceled") &&
  session.active_files === 0 &&
  session.failed_files === 0;

const getErrorStatus = (error: unknown) => {
  if (!error || typeof error !== "object") return undefined;
  const { response, status } = error as { response?: unknown; status?: unknown };
  if (typeof status === "number") return status;
  if (!response || typeof response !== "object") return undefined;
  const { status: responseStatus } = response as { status?: unknown };
  return typeof responseStatus === "number" ? responseStatus : undefined;
};

type DocumentsTabFilters = {
  order: DocumentListOrder;
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
    q: "",
    sort: "created_at",
    status: "",
  };
  const activeSessionId = useUploadSessionStore((state) => state.activeSessionIds[name] ?? null);
  const clearActiveSessionId = useUploadSessionStore((state) => state.clearActiveSessionId);
  const setActiveSessionId = useUploadSessionStore((state) => state.setActiveSessionId);

  const { data: collection } = useCollection(name);
  const documentFilters: DocumentListFilters = {
    limit: pageSize,
    order: activeFilters.order,
    q: activeFilters.q,
    sort: activeFilters.sort,
    status: activeFilters.status,
  };
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isError,
    isFetchingNextPage,
    isPending,
    refetch,
  } = useInfiniteDocuments(name, documentFilters);
  const uploadSession = useUploadSession(name, activeSessionId);
  const cancelSession = useCancelUploadSession(name);
  const remove = useDeleteDocument(name);
  const batchRemove = useBatchDeleteDocuments(name);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const [deleteDoc, setDeleteDoc] = useState<{ id: string; filename: string } | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const allowed = getAllowedFileTypes(collection?.metadata);
  const accept = acceptAttribute(allowed);
  const documentPages = useMemo(() => data?.pages ?? [], [data?.pages]);
  const documents = useMemo(() => documentPages.flatMap((page) => page.documents), [documentPages]);
  const total = documentPages.find((page) => page.total !== null)?.total ?? null;
  const canFetchNextPage = Boolean(hasNextPage && !isFetchingNextPage && !isPending && !isError);
  const dismissCompletedUploadSession = uploadSession.data
    ? shouldDismissUploadSession(uploadSession.data)
    : false;

  const {
    upload,
    dragging,
    setDragging,
    fileInput,
    folderInput,
    workerAvailability,
    workerOffline,
    onFiles,
    onDrop,
  } = useDocumentUpload({ name, allowed, setActiveSessionId });

  const {
    selected,
    selectedDocuments,
    allVisibleSelected,
    toggleVisibleSelection,
    toggleDocumentSelection,
    clearSelection,
  } = useDocumentsTabState(documents);

  useEffect(() => {
    if (uploadSession.isError && getErrorStatus(uploadSession.error) === 404) {
      clearActiveSessionId(name);
    }
  }, [clearActiveSessionId, name, uploadSession.error, uploadSession.isError]);

  useEffect(() => {
    if (uploadSession.data && shouldDismissUploadSession(uploadSession.data)) {
      clearActiveSessionId(name);
    }
  }, [clearActiveSessionId, name, uploadSession.data]);

  useInfiniteScroll(loadMoreRef, {
    enabled: canFetchNextPage,
    onLoadMore: () => void fetchNextPage(),
  });

  const updateFilters = (next: Partial<DocumentsTabFilters>) => {
    onFiltersChange?.(next);
  };

  const acceptedDescription = allowed.length
    ? `Only ${allowed.map((t) => `.${t}`).join(", ")} allowed in this collection.`
    : "PDF, DOCX, PPTX, MD, HTML, TXT, images — ingested automatically.";

  const loadedLabel =
    total == null
      ? `${documents.length.toLocaleString()} loaded document${documents.length === 1 ? "" : "s"}`
      : `${total.toLocaleString()} matching document${total === 1 ? "" : "s"}`;

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

      {activeSessionId && uploadSession.data && !dismissCompletedUploadSession && (
        <UploadSessionPanel
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

      <DocumentsToolbar
        q={activeFilters.q}
        status={activeFilters.status}
        sort={activeFilters.sort}
        order={activeFilters.order}
        onFiltersChange={updateFilters}
        loadedLabel={loadedLabel}
        selectedCount={selected.size}
        onClearSelection={clearSelection}
        onBulkDelete={() => setBulkDeleteOpen(true)}
      />

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
      ) : documents.length === 0 ? (
        <DocumentsEmptyState filtered={Boolean(activeFilters.q || activeFilters.status)} />
      ) : (
        <DocumentsTable
          name={name}
          documents={documents}
          total={total}
          selected={selected}
          allVisibleSelected={allVisibleSelected}
          onToggleVisibleSelection={toggleVisibleSelection}
          onToggleDocumentSelection={toggleDocumentSelection}
          onDelete={setDeleteDoc}
        />
      )}

      {documents.length > 0 && (
        <div ref={loadMoreRef} className="flex items-center justify-center py-2">
          {hasNextPage ? (
            <Button
              disabled={isFetchingNextPage}
              size="sm"
              variant="secondary"
              onClick={() => fetchNextPage()}
            >
              {isFetchingNextPage && <Spinner size="sm" />}
              {isFetchingNextPage ? "Loading more" : "Load more"}
            </Button>
          ) : (
            <span className="text-sm text-muted-foreground">All matching documents loaded</span>
          )}
        </div>
      )}

      <DeleteDocumentDialogs
        deleteDoc={deleteDoc}
        onCloseDelete={() => setDeleteDoc(null)}
        onConfirmDelete={async (id) => {
          await remove.mutateAsync(id);
          setDeleteDoc(null);
        }}
        deletePending={remove.isPending}
        bulkOpen={bulkDeleteOpen}
        onCloseBulk={() => setBulkDeleteOpen(false)}
        onConfirmBulk={async (ids) => {
          await batchRemove.mutateAsync(ids);
          clearSelection();
          setBulkDeleteOpen(false);
        }}
        bulkPending={batchRemove.isPending}
        selectedDocuments={selectedDocuments}
      />
    </div>
  );
};
