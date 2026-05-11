import { createFileRoute, Link } from "@tanstack/react-router";
import { CheckCircle2, CircleAlert, FileText, FolderOpen, Trash2, Upload, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useCollection } from "@/hooks/use-collections";
import {
  useCancelUploadSession,
  useDeleteDocument,
  useDocuments,
  useUploadSession,
  useUploadSessionDocuments,
} from "@/hooks/use-documents";
import { cn } from "@/lib/cn";
import { acceptAttribute, filterBlockedFiles, getAllowedFileTypes } from "@/lib/file-types";
import { formatBytes, formatRelative } from "@/lib/format";
import type { DocumentStatus, UploadSession } from "@/types/rag-computer";

export const Route = createFileRoute("/_dashboard/collections/$name/documents/")({
  component: () => <DocumentsTab />,
});

const statusVariant: Record<DocumentStatus, "success" | "warning" | "info" | "error"> = {
  ready: "success",
  processing: "info",
  pending: "warning",
  failed: "error",
};

const DocumentsTab = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);
  const sessionStorageKey = useMemo(() => `rag-computer:upload-session:${name}`, [name]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(sessionStorageKey),
  );

  const { data: collection } = useCollection(name);
  const { data, isPending } = useDocuments(name);
  const uploadSession = useUploadSession(name, activeSessionId);
  const upload = useUploadSessionDocuments(name, {
    onSessionStart: (session) => setActiveSessionId(session.id),
  });
  const cancelSession = useCancelUploadSession(name);
  const remove = useDeleteDocument(name);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [deleteDoc, setDeleteDoc] = useState<{ id: string; filename: string } | null>(null);

  const allowed = getAllowedFileTypes(collection?.metadata);
  const accept = acceptAttribute(allowed);

  useUploadSessionStorage(activeSessionId, sessionStorageKey);

  const onFiles = useCallback(
    async (files: FileList | File[]) => {
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
        setActiveSessionId(res.session.id);
        if (fileInput.current) fileInput.current.value = "";
        if (folderInput.current) folderInput.current.value = "";
      }
    },
    [upload, allowed],
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
          dragging && "border-primary bg-accent",
          upload.isPending && "pointer-events-none opacity-60",
        )}
      >
        <div className="flex items-center gap-3">
          <Upload className="size-5 text-muted-foreground" />
          <div className="flex flex-col items-start gap-0.5">
            <span className="font-medium">
              {upload.isPending ? "Uploading…" : "Drop files here"}
            </span>
            <span className="text-xs text-muted-foreground">{acceptedDescription}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button disabled={upload.isPending} onClick={() => fileInput.current?.click()} size="sm">
            <Upload className="size-4" />
            Files
          </Button>
          <Button
            disabled={upload.isPending}
            onClick={() => folderInput.current?.click()}
            size="sm"
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
          onChange={(e) => e.target.files && onFiles(e.target.files)}
        />
        <input
          ref={folderInput}
          type="file"
          multiple
          className="sr-only"
          accept={accept}
          onChange={(e) => e.target.files && onFiles(e.target.files)}
          {...{ webkitdirectory: "", directory: "" }}
        />
      </fieldset>

      {activeSessionId && uploadSession.data && (
        <UploadSessionProgressPanel
          loadingCancel={cancelSession.isPending}
          onCancel={() => cancelSession.mutate(activeSessionId)}
          onDismiss={() => setActiveSessionId(null)}
          session={uploadSession.data}
          streaming={uploadSession.streaming}
        />
      )}

      {activeSessionId && !uploadSession.data && (
        <Card className="overflow-hidden rounded-xl">
          <CardContent className="flex items-center gap-3 p-4">
            <Spinner size="sm" />
            <span className="text-sm text-muted-foreground">Loading upload session…</span>
          </CardContent>
        </Card>
      )}

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : data?.documents.length === 0 ? (
        <Empty
          icon={<FileText className="size-6" />}
          title="No documents yet"
          description="Upload files above — they'll appear here as they ingest."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 border-b border-border px-4 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            <span>Filename</span>
            <span className="text-right">Size</span>
            <span className="text-right">Chunks</span>
            <span className="text-right">Updated</span>
            <span className="w-6" />
          </div>
          <ul className="divide-y divide-border">
            {data?.documents.map((d) => (
              <li
                key={d.id}
                className="group grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-4 px-4 py-3 hover:bg-muted"
              >
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
    </div>
  );
};

const useUploadSessionStorage = (activeSessionId: string | null, sessionStorageKey: string) => {
  useEffect(() => {
    if (!activeSessionId) {
      window.localStorage.removeItem(sessionStorageKey);
      return;
    }
    window.localStorage.setItem(sessionStorageKey, activeSessionId);
  }, [activeSessionId, sessionStorageKey]);
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
