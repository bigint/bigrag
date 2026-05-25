import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { DeleteDocumentDialogs } from "@/features/collections/documents/delete-document-dialogs";
import { DocumentUploadDropzone } from "@/features/collections/documents/document-upload-dropzone";
import { DocumentsEmptyState } from "@/features/collections/documents/documents-empty-state";
import {
  acceptedDescription,
  type DocumentsTabFilters,
  defaultDocumentsTabFilters,
  documentsPageSize,
  getErrorStatus,
  shouldDismissUploadSession,
} from "@/features/collections/documents/documents-tab-model";
import { DocumentsTable } from "@/features/collections/documents/documents-table";
import { DocumentsToolbar } from "@/features/collections/documents/documents-toolbar";
import { UploadSessionPanel } from "@/features/collections/documents/upload-session-panel";
import {
  UploadSessionErrorCard,
  UploadSessionLoadingCard,
} from "@/features/collections/documents/upload-session-status-cards";
import { useDocumentUpload } from "@/features/collections/documents/use-document-upload";
import { useDocumentsTabState } from "@/features/collections/documents/use-documents-tab-state";
import { useUploadSessionStore } from "@/features/collections/upload-session-store";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { useCollection } from "@/hooks/use-collections";
import {
  type DocumentListFilters,
  useBatchDeleteDocuments,
  useCancelUploadSession,
  useDeleteDocument,
  useInfiniteDocuments,
  useUploadSession,
} from "@/hooks/use-documents";
import { useInfiniteScroll } from "@/hooks/use-infinite-scroll";
import { acceptAttribute, getAllowedFileTypes } from "@/lib/file-types";

type DocumentsTabProps = {
  filters?: DocumentsTabFilters;
  name: string;
  onFiltersChange?: (filters: Partial<DocumentsTabFilters>) => void;
};

export const DocumentsTab = ({ filters, name, onFiltersChange }: DocumentsTabProps) => {
  const activeFilters = filters ?? defaultDocumentsTabFilters;
  const activeSessionId = useUploadSessionStore((state) => state.activeSessionIds[name] ?? null);
  const clearActiveSessionId = useUploadSessionStore((state) => state.clearActiveSessionId);
  const setActiveSessionId = useUploadSessionStore((state) => state.setActiveSessionId);

  const { data: collection } = useCollection(name);
  const documentFilters: DocumentListFilters = {
    limit: documentsPageSize,
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
    isFetching,
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

  const loadedLabel =
    total == null
      ? `${documents.length.toLocaleString()} loaded document${documents.length === 1 ? "" : "s"}`
      : `${total.toLocaleString()} matching document${total === 1 ? "" : "s"}`;

  return (
    <div className="flex flex-col gap-4">
      <WorkerOfflineBanner availability={workerAvailability} />
      <DocumentUploadDropzone
        accept={accept}
        acceptedDescription={acceptedDescription(allowed)}
        dragging={dragging}
        fileInput={fileInput}
        folderInput={folderInput}
        onDrop={onDrop}
        onFiles={onFiles}
        setDragging={setDragging}
        uploadPending={upload.isPending}
        workerAvailability={workerAvailability}
        workerOffline={workerOffline}
      />

      {activeSessionId && uploadSession.data && !dismissCompletedUploadSession && (
        <UploadSessionPanel
          loadingCancel={cancelSession.isPending}
          onCancel={() => cancelSession.mutate(activeSessionId)}
          onDismiss={() => clearActiveSessionId(name)}
          session={uploadSession.data}
        />
      )}

      {activeSessionId && uploadSession.isError && getErrorStatus(uploadSession.error) !== 404 && (
        <UploadSessionErrorCard
          message={
            uploadSession.error instanceof Error
              ? uploadSession.error.message
              : "Upload session unavailable"
          }
          onDismiss={() => clearActiveSessionId(name)}
          onRetry={() => uploadSession.refetch()}
        />
      )}

      {activeSessionId && !uploadSession.data && uploadSession.isPending && (
        <UploadSessionLoadingCard />
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
        onRefresh={() => {
          void refetch();
        }}
        refreshPending={isFetching && !isFetchingNextPage}
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
