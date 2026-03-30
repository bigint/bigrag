"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Inbox,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
  XCircle
} from "lucide-react";
import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import {
  deleteDocument,
  reprocessDocument,
  uploadDocument
} from "@/lib/api";
import { getBaseUrl, getSessionToken } from "@/lib/auth-store";
import { collectionQueryOptions, documentsQueryOptions } from "@/lib/queries";
import { cn, formatBytes, timeAgo } from "@/lib/utils";

// --- Upload tracker types ---

interface UploadProgress {
  id: string;
  filename: string;
  fileSize: number;
  phase: "uploading" | "processing" | "complete" | "failed";
  step: string;
  message: string;
  progress: number;
  events: ProgressEvent[];
  startedAt: number;
}

interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  time: number;
  detail?: Record<string, unknown>;
}

// --- Status colors ---

const STATUS_COLORS: Record<string, string> = {
  ready: "bg-bg-hover text-text",
  processing: "bg-bg-hover text-text-muted",
  pending: "bg-bg-hover text-text-muted",
  failed: "bg-bg-hover text-text"
};

const PHASE_COLORS: Record<string, string> = {
  uploading: "text-text",
  processing: "text-text-muted",
  complete: "text-text",
  failed: "text-text"
};

// --- SSE hook ---

function useIngestionSSE(
  collectionName: string,
  documentId: string | null,
  onEvent: (data: Record<string, unknown>) => void
) {
  useEffect(() => {
    if (!documentId) return;
    const url = `${getBaseUrl()}/v1/collections/${encodeURIComponent(collectionName)}/documents/${documentId}/progress`;
    const es = new EventSource(url);
    es.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        // ignore parse errors
      }
    };
    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, [collectionName, documentId, onEvent]);
}

// --- Progress bar component ---

const ProgressBar = ({ value }: { readonly value: number }) => (
  <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-hover">
    <div
      className="h-full rounded-full bg-accent transition-all duration-500 ease-out"
      style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
    />
  </div>
);

// --- Upload tracker card ---

const UploadTracker = ({
  upload,
  onDismiss
}: {
  readonly upload: UploadProgress;
  readonly onDismiss: () => void;
}) => {
  const [expanded, setExpanded] = useState(true);
  const elapsed = ((Date.now() - upload.startedAt) / 1000).toFixed(1);

  return (
    <div
      className={cn(
        "rounded-lg border bg-bg-card overflow-hidden transition-colors",
        upload.phase === "failed" ? "border-danger/30" : "border-border"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-bg-hover">
          {upload.phase === "uploading" && <Upload className="size-4 text-accent animate-pulse" />}
          {upload.phase === "processing" && <Loader2 className="size-4 text-warning animate-spin" />}
          {upload.phase === "complete" && <Check className="size-4 text-success" />}
          {upload.phase === "failed" && <XCircle className="size-4 text-danger" />}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium text-text">{upload.filename}</p>
            <span className="shrink-0 text-[11px] text-text-dim">{formatBytes(upload.fileSize)}</span>
          </div>
          <p className={cn("text-xs", PHASE_COLORS[upload.phase])}>
            {upload.message}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-xs text-text-dim">{elapsed}s</span>
          {(upload.phase === "complete" || upload.phase === "failed") && (
            <button
              className="rounded-md p-1 text-text-dim hover:bg-bg-hover hover:text-text"
              onClick={onDismiss}
              type="button"
            >
              <XCircle className="size-3.5" />
            </button>
          )}
          <button
            className="rounded-md p-1 text-text-dim hover:bg-bg-hover hover:text-text"
            onClick={() => setExpanded(!expanded)}
            type="button"
          >
            {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      {upload.phase !== "complete" && upload.phase !== "failed" && (
        <div className="px-4 pb-2">
          <ProgressBar value={upload.progress} />
          <p className="mt-1 text-right font-mono text-[11px] text-text-dim">
            {Math.round(upload.progress * 100)}%
          </p>
        </div>
      )}

      {/* Event log */}
      {expanded && upload.events.length > 0 && (
        <div className="border-t border-border bg-bg/50 px-4 py-2 max-h-48 overflow-y-auto">
          <div className="space-y-1">
            {upload.events.map((ev, i) => (
              <div className="flex items-start gap-2 text-[11px]" key={i}>
                <span className="shrink-0 font-mono text-text-dim">
                  {((ev.time - upload.startedAt) / 1000).toFixed(1)}s
                </span>
                <span className="shrink-0 rounded bg-bg-hover px-1 py-0.5 font-mono text-text-dim">
                  {ev.step}
                </span>
                <span className="text-text-muted">{ev.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// --- Main page ---

const CollectionDetailPage = ({ params }: { readonly params: Promise<{ name: string }> }) => {
  const { name } = use(params);
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<Map<string, UploadProgress>>(new Map());
  const [dragging, setDragging] = useState(false);

  const collectionQuery = useQuery(collectionQueryOptions(name));
  const documentsQuery = useQuery(documentsQueryOptions(name));

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(name, docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", name] });
      queryClient.invalidateQueries({ queryKey: ["collection", name] });
    }
  });

  const reprocessMutation = useMutation({
    mutationFn: (docId: string) => reprocessDocument(name, docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", name] })
  });

  // Connect SSE for each processing upload
  const activeDocIds = [...uploads.values()]
    .filter((u) => u.phase === "processing")
    .map((u) => u.id);

  // SSE event handler
  const handleSSEEvent = useCallback(
    (docId: string, data: Record<string, unknown>) => {
      setUploads((prev) => {
        const next = new Map(prev);
        const upload = next.get(docId);
        if (!upload) return prev;

        const event: ProgressEvent = {
          step: String(data.step ?? ""),
          message: String(data.message ?? ""),
          progress: Number(data.progress ?? 0),
          time: Date.now(),
          detail: data
        };

        const updated: UploadProgress = {
          ...upload,
          step: event.step,
          message: event.message,
          progress: event.progress,
          events: [...upload.events, event]
        };

        if (data.status === "complete") {
          updated.phase = "complete";
          updated.progress = 1;
          queryClient.invalidateQueries({ queryKey: ["documents", name] });
          queryClient.invalidateQueries({ queryKey: ["collection", name] });
        } else if (data.status === "failed") {
          updated.phase = "failed";
        }

        next.set(docId, updated);
        return next;
      });
    },
    [name, queryClient]
  );

  // SSE connections for each active document
  useEffect(() => {
    if (activeDocIds.length === 0) return;

    const sources: EventSource[] = [];

    for (const docId of activeDocIds) {
      const url = `${getBaseUrl()}/v1/collections/${encodeURIComponent(name)}/documents/${docId}/progress`;
      const es = new EventSource(url);

      es.onmessage = (e) => {
        try {
          handleSSEEvent(docId, JSON.parse(e.data));
        } catch {
          // ignore
        }
      };

      es.onerror = () => es.close();
      sources.push(es);
    }

    return () => sources.forEach((s) => s.close());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDocIds.join(","), name, handleSSEEvent]);

  const handleUpload = useCallback(
    async (files: FileList | null) => {
      if (!files?.length) return;

      for (const file of Array.from(files)) {
        const tempId = crypto.randomUUID();

        // Add uploading tracker
        setUploads((prev) => {
          const next = new Map(prev);
          next.set(tempId, {
            id: tempId,
            filename: file.name,
            fileSize: file.size,
            phase: "uploading",
            step: "uploading",
            message: "Uploading file...",
            progress: 0,
            events: [{ step: "upload", message: "Starting upload", progress: 0, time: Date.now() }],
            startedAt: Date.now()
          });
          return next;
        });

        try {
          const doc = await uploadDocument(name, file);

          // Switch from temp ID to real doc ID, move to processing phase
          setUploads((prev) => {
            const next = new Map(prev);
            const old = next.get(tempId);
            next.delete(tempId);
            if (old) {
              next.set(doc.id, {
                ...old,
                id: doc.id,
                phase: "processing",
                step: "queued",
                message: "Queued for processing",
                progress: 0.05,
                events: [
                  ...old.events,
                  { step: "uploaded", message: `File uploaded (${formatBytes(file.size)})`, progress: 0.05, time: Date.now() }
                ]
              });
            }
            return next;
          });

          queryClient.invalidateQueries({ queryKey: ["documents", name] });
        } catch (err) {
          setUploads((prev) => {
            const next = new Map(prev);
            const old = next.get(tempId);
            if (old) {
              next.set(tempId, {
                ...old,
                phase: "failed",
                step: "upload_failed",
                message: err instanceof Error ? err.message : "Upload failed",
                events: [
                  ...old.events,
                  { step: "error", message: String(err), progress: 0, time: Date.now() }
                ]
              });
            }
            return next;
          });
        }
      }
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [name, queryClient]
  );

  const dismissUpload = useCallback((id: string) => {
    setUploads((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const collection = collectionQuery.data;
  const documents = documentsQuery.data?.documents ?? [];
  const activeUploads = [...uploads.values()];

  return (
    <div>
      <div className="mb-6">
        <Link
          className="mb-3 inline-flex items-center gap-1 text-sm text-text-muted transition-colors hover:text-text"
          href="/collections"
        >
          <ArrowLeft className="size-3.5" />
          Collections
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-mono text-xl font-semibold text-text">{name}</h1>
            {collection?.description && (
              <p className="mt-1 text-sm text-text-muted">{collection.description}</p>
            )}
          </div>
          <div>
            <input
              accept="*/*"
              className="hidden"
              multiple
              onChange={(e) => handleUpload(e.target.files)}
              ref={fileInputRef}
              type="file"
            />
            <button
              className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90"
              onClick={() => fileInputRef.current?.click()}
              type="button"
            >
              <Upload className="size-4" />
              Upload Documents
            </button>
          </div>
        </div>
      </div>

      {collection && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Documents</p>
            <p className="mt-1 font-mono text-lg font-semibold">{collection.document_count}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Model</p>
            <p className="mt-1 font-mono text-sm">{collection.embedding_model}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Dimension</p>
            <p className="mt-1 font-mono text-lg font-semibold">{collection.dimension}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Chunk Size</p>
            <p className="mt-1 font-mono text-lg font-semibold">{collection.chunk_size}</p>
          </div>
        </div>
      )}

      {/* Drop zone */}
      <div
        className={cn(
          "mb-6 flex flex-col items-center justify-center rounded-lg border-2 border-dashed py-8 transition-all",
          dragging
            ? "border-accent bg-accent/5 scale-[1.01]"
            : "border-border hover:border-border-hover"
        )}
        onDragEnter={() => setDragging(true)}
        onDragLeave={() => setDragging(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleUpload(e.dataTransfer.files);
        }}
      >
        <Upload className={cn("mb-2 size-8", dragging ? "text-accent" : "text-text-dim")} />
        <p className="text-sm text-text-muted">
          Drop files here or{" "}
          <button
            className="text-accent hover:underline"
            onClick={() => fileInputRef.current?.click()}
            type="button"
          >
            browse
          </button>
        </p>
        <p className="mt-1 text-xs text-text-dim">
          Supports PDF, DOCX, PPTX, HTML, Markdown, images, and more
        </p>
      </div>

      {/* Active uploads with real-time progress */}
      {activeUploads.length > 0 && (
        <div className="mb-6 space-y-3">
          <h2 className="text-sm font-medium text-text">Active Uploads</h2>
          {activeUploads.map((upload) => (
            <UploadTracker
              key={upload.id}
              onDismiss={() => dismissUpload(upload.id)}
              upload={upload}
            />
          ))}
        </div>
      )}

      {/* Documents list */}
      <div className="rounded-lg border border-border bg-bg-card">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-sm font-medium text-text">Documents</h2>
        </div>

        {documentsQuery.isLoading ? (
          <div className="divide-y divide-border">
            {Array.from({ length: 3 }).map((_, i) => (
              <div className="flex items-center gap-4 px-5 py-3.5" key={i}>
                <div className="h-4 w-40 animate-pulse rounded bg-bg-hover" />
                <div className="ml-auto h-4 w-16 animate-pulse rounded bg-bg-hover" />
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center py-12">
            <Inbox className="mb-2 size-8 text-text-dim" />
            <p className="text-sm text-text-dim">No documents uploaded yet</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border text-left text-[13px] text-text-dim">
                <th className="px-5 py-3 font-medium">File</th>
                <th className="px-5 py-3 font-medium">Type</th>
                <th className="px-5 py-3 text-right font-medium">Size</th>
                <th className="px-5 py-3 text-right font-medium">Chunks</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 text-right font-medium">Uploaded</th>
                <th className="px-5 py-3 text-right font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {documents.map((doc) => (
                <tr className="group" key={doc.id}>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <FileText className="size-4 shrink-0 text-text-dim" />
                      <span className="truncate text-sm text-text">{doc.filename}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs uppercase text-text-muted">
                    {doc.file_type || "—"}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-sm text-text-muted">
                    {formatBytes(doc.file_size)}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono text-sm text-text-muted">
                    {doc.chunk_count}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
                        STATUS_COLORS[doc.status] ?? STATUS_COLORS.pending
                      )}
                    >
                      {doc.status === "processing" && (
                        <Loader2 className="size-3 animate-spin" />
                      )}
                      {doc.status === "failed" && <XCircle className="size-3" />}
                      {doc.status === "ready" && <Check className="size-3" />}
                      {doc.status}
                    </span>
                    {doc.error_message && (
                      <p className="mt-0.5 max-w-xs truncate text-[11px] text-danger">
                        {doc.error_message}
                      </p>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-right text-sm text-text-muted">
                    {timeAgo(doc.created_at)}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      {doc.status === "failed" && (
                        <button
                          className="rounded-md p-1 text-text-dim hover:bg-bg-hover hover:text-text"
                          onClick={() => reprocessMutation.mutate(doc.id)}
                          title="Reprocess"
                          type="button"
                        >
                          <RefreshCw className="size-3.5" />
                        </button>
                      )}
                      <button
                        className="rounded-md p-1 text-text-dim hover:bg-danger/10 hover:text-danger"
                        onClick={() => {
                          if (confirm(`Delete "${doc.filename}"?`))
                            deleteMutation.mutate(doc.id);
                        }}
                        title="Delete"
                        type="button"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default CollectionDetailPage;
