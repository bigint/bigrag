"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  Download,
  FileText,
  Loader2,
  XCircle
} from "lucide-react";
import Link from "next/link";
import { use } from "react";
import {
  type Document,
  getDocument,
  getDocumentChunks,
  getDocumentFileUrl
} from "@/lib/api";
import { cn, formatBytes, timeAgo } from "@/lib/utils";
import { match } from "ts-pattern";

const DocumentDetailPage = ({
  params
}: {
  readonly params: Promise<{ name: string; documentId: string }>;
}) => {
  const { name, documentId } = use(params);

  const docQuery = useQuery({
    queryFn: () => getDocument(name, documentId),
    queryKey: ["document", name, documentId]
  });

  const chunksQuery = useQuery({
    enabled: docQuery.data?.status === "ready",
    queryFn: () => getDocumentChunks(name, documentId),
    queryKey: ["chunks", name, documentId]
  });

  const doc = docQuery.data;
  const chunks = chunksQuery.data?.chunks ?? [];

  return (
    <div>
      <div className="mb-6">
        <Link
          className="mb-3 inline-flex items-center gap-1 text-sm text-text-muted transition-colors hover:text-text"
          href={`/collections/${encodeURIComponent(name)}`}
        >
          <ArrowLeft className="size-3.5" />
          {name}
        </Link>

        {doc ? (
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-bg-hover">
                <FileText className="size-5 text-text-dim" />
              </div>
              <div>
                <h1 className="font-mono text-lg font-semibold text-text">
                  {doc.filename}
                </h1>
                <p className="text-sm text-text-muted">
                  {formatBytes(doc.file_size)} &middot;{" "}
                  {doc.file_type.toUpperCase()} &middot; {timeAgo(doc.created_at)}
                </p>
              </div>
            </div>
            {doc.status === "ready" && (
              <a
                className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-muted transition-colors hover:bg-bg-hover hover:text-text"
                href={getDocumentFileUrl(name, doc.id)}
                rel="noopener noreferrer"
                target="_blank"
              >
                <Download className="size-3.5" />
                Original
              </a>
            )}
          </div>
        ) : (
          <div className="h-10 w-64 animate-pulse rounded bg-bg-hover" />
        )}
      </div>

      {/* Info cards */}
      {doc && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Status</p>
            <div className="mt-1 flex items-center gap-1.5">
              {match(doc.status)
                .with("ready", () => <Check className="size-3.5 text-success" />)
                .with("processing", () => <Loader2 className="size-3.5 text-warning animate-spin" />)
                .with("failed", () => <XCircle className="size-3.5 text-danger" />)
                .otherwise(() => null)}
              <span className="font-mono text-sm">{doc.status}</span>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Chunks</p>
            <p className="mt-1 font-mono text-lg font-semibold">
              {doc.chunk_count}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">File Size</p>
            <p className="mt-1 font-mono text-sm">{formatBytes(doc.file_size)}</p>
          </div>
          <div className="rounded-lg border border-border bg-bg-card p-4">
            <p className="text-[11px] uppercase text-text-dim">Type</p>
            <p className="mt-1 font-mono text-sm uppercase">{doc.file_type}</p>
          </div>
        </div>
      )}

      {/* Error message */}
      {doc?.error_message && (
        <div className="mb-6 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3">
          <p className="text-sm text-danger">{doc.error_message}</p>
        </div>
      )}

      {/* Metadata */}
      {doc?.metadata && Object.keys(doc.metadata).length > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-bg-card">
          <div className="border-b border-border px-5 py-3">
            <h2 className="text-sm font-medium text-text">Metadata</h2>
          </div>
          <pre className="overflow-x-auto px-5 py-3 font-mono text-xs text-text-muted">
            {JSON.stringify(doc.metadata, null, 2)}
          </pre>
        </div>
      )}

      {/* Chunks */}
      <div className="rounded-lg border border-border bg-bg-card">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-sm font-medium text-text">
            Processed Chunks
            {chunksQuery.data && (
              <span className="ml-2 text-text-dim">({chunksQuery.data.total})</span>
            )}
          </h2>
        </div>

        {chunksQuery.isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-5 animate-spin text-text-dim" />
          </div>
        ) : chunks.length === 0 ? (
          <div className="py-12 text-center text-sm text-text-dim">
            {doc?.status === "ready"
              ? "No chunks found"
              : "Chunks available after processing completes"}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {chunks.map((chunk) => (
              <div className="px-5 py-4" key={chunk.id}>
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded bg-bg-hover px-1.5 py-0.5 font-mono text-[11px] text-text-dim">
                    #{chunk.chunk_index}
                  </span>
                  <span className="font-mono text-[11px] text-text-dim">
                    {chunk.text.length} chars
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-muted">
                  {chunk.text}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentDetailPage;
