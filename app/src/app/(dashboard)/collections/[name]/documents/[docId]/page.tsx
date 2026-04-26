"use client";

import { ArrowLeft, RefreshCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import {
  useChunks,
  useDeleteDocument,
  useDocument,
  useReprocessDocument,
} from "@/hooks/use-documents";
import { cn } from "@/lib/cn";
import { formatBytes, formatRelative } from "@/lib/format";
import type { ProgressEvent } from "@/types/bigrag";

const useProgressStream = (
  collection: string,
  docId: string,
  enabled: boolean,
): ProgressEvent | null => {
  const [event, setEvent] = useState<ProgressEvent | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource(
      `/api/bigrag/v1/collections/${encodeURIComponent(collection)}/documents/${docId}/progress`,
    );
    es.onmessage = (e) => {
      try {
        setEvent(JSON.parse(e.data) as ProgressEvent);
      } catch {}
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [collection, docId, enabled]);

  return event;
};

const DocumentDetail = ({ params }: { params: Promise<{ name: string; docId: string }> }) => {
  const { name: rawName, docId } = use(params);
  const name = decodeURIComponent(rawName);
  const router = useRouter();

  const { data: doc, isPending } = useDocument(name, docId);
  const { data: chunks } = useChunks(name, docId);
  const reprocess = useReprocessDocument(name);
  const remove = useDeleteDocument(name);

  const streaming = doc?.status === "pending" || doc?.status === "processing";
  const progress = useProgressStream(name, docId, !!streaming);
  const pct = Math.round((progress?.progress ?? 0) * 100);

  if (isPending || !doc) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href={`/collections/${encodeURIComponent(name)}/documents`}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Documents
      </Link>

      <PageHeader
        eyebrow={`${doc.file_type.toUpperCase()} · ${formatBytes(doc.file_size)}`}
        title={doc.filename}
        description={`${doc.chunk_count} chunks · updated ${formatRelative(doc.updated_at)}`}
        actions={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={async () => {
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
            <Button
              variant="destructive"
              onClick={async () => {
                if (!confirm(`Delete "${doc.filename}"?`)) return;
                await remove.mutateAsync(docId);
                router.replace(`/collections/${encodeURIComponent(name)}/documents`);
              }}
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </Button>
          </div>
        }
      />

      {streaming && (
        <Card>
          <CardContent className="flex flex-col gap-2 pt-5">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium capitalize">{progress?.step ?? "queued"}</span>
              <span className="tabular-nums text-muted-foreground">{pct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-[width] duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
            {progress?.message && (
              <p className="text-xs text-muted-foreground">{progress.message}</p>
            )}
          </CardContent>
        </Card>
      )}

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
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Chunks
        </h2>
        {!chunks ? (
          <Spinner />
        ) : chunks.chunks.length === 0 ? (
          <Empty title="No chunks yet" description="Ingestion may still be in progress." />
        ) : (
          <div className="flex flex-col gap-2">
            {chunks.chunks.map((c) => (
              <article key={c.id} className={cn("rounded-xl border border-border bg-card p-4")}>
                <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="neutral">#{c.chunk_index}</Badge>
                  <span className="font-mono">{c.id.slice(0, 8)}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{c.text}</p>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentDetail;
