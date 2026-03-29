"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  FileText,
  Inbox,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
  XCircle
} from "lucide-react";
import Link from "next/link";
import { use, useCallback, useRef, useState } from "react";
import {
  deleteDocument,
  reprocessDocument,
  uploadDocument
} from "@/lib/api";
import { collectionQueryOptions, documentsQueryOptions } from "@/lib/queries";
import { cn, formatBytes, timeAgo } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  ready: "bg-success/10 text-success",
  processing: "bg-warning/10 text-warning",
  pending: "bg-bg-hover text-text-muted",
  failed: "bg-danger/10 text-danger"
};

const CollectionDetailPage = ({ params }: { readonly params: Promise<{ name: string }> }) => {
  const { name } = use(params);
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const collectionQuery = useQuery(collectionQueryOptions(name));
  const documentsQuery = useQuery({
    ...documentsQueryOptions(name),
    refetchInterval: 5000
  });

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

  const handleUpload = useCallback(
    async (files: FileList | null) => {
      if (!files?.length) return;
      setUploading(true);
      try {
        for (const file of Array.from(files)) {
          await uploadDocument(name, file);
        }
        queryClient.invalidateQueries({ queryKey: ["documents", name] });
        queryClient.invalidateQueries({ queryKey: ["collection", name] });
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [name, queryClient]
  );

  const collection = collectionQuery.data;
  const documents = documentsQuery.data?.documents ?? [];

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
              className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              type="button"
            >
              {uploading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Upload className="size-4" />
              )}
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
        className="mb-6 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border py-8 transition-colors hover:border-border-hover"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleUpload(e.dataTransfer.files);
        }}
      >
        <Upload className="mb-2 size-8 text-text-dim" />
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
