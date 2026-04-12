"use client";

import { FileText, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { use, useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useCollection } from "@/hooks/use-collections";
import { useDeleteDocument, useDocuments, useUploadDocuments } from "@/hooks/use-documents";
import { cn } from "@/lib/cn";
import { acceptAttribute, filterBlockedFiles, getAllowedFileTypes } from "@/lib/file-types";
import { formatBytes, formatRelative } from "@/lib/format";
import type { DocumentStatus } from "@/types/bigrag";

const statusVariant: Record<DocumentStatus, "success" | "warning" | "info" | "error"> = {
  ready: "success",
  processing: "info",
  pending: "warning",
  failed: "error",
};

const DocumentsTab = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);

  const { data: collection } = useCollection(name);
  const { data, isPending } = useDocuments(name);
  const upload = useUploadDocuments(name);
  const remove = useDeleteDocument(name);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [deleteDoc, setDeleteDoc] = useState<{ id: string; filename: string } | null>(null);

  const allowed = getAllowedFileTypes(collection?.metadata);
  const accept = acceptAttribute(allowed);

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
      if (accepted.length) await upload.mutateAsync(accepted);
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
      <label
        htmlFor="doc-upload"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-8 text-sm transition-colors",
          "border-border bg-card hover:border-primary hover:bg-accent/50",
          dragging && "border-primary bg-accent",
          upload.isPending && "pointer-events-none opacity-60",
        )}
      >
        <Upload className="size-5 text-muted-foreground" />
        <div className="flex flex-col items-center gap-0.5 text-center">
          <span className="font-medium">
            {upload.isPending ? "Uploading…" : "Drop files or click to upload"}
          </span>
          <span className="text-xs text-muted-foreground">{acceptedDescription}</span>
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
      </label>

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
                  href={`/collections/${encodeURIComponent(name)}/documents/${d.id}`}
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

const FileType = ({ type }: { type: string }) => (
  <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
    {type.slice(0, 4) || "?"}
  </div>
);

export default DocumentsTab;
