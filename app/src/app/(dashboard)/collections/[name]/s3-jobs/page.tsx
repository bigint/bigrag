"use client";

import { Cloud, Plus, RefreshCw, Trash2 } from "lucide-react";
import { use, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useDeleteS3Job, useResyncS3Job, useS3Jobs } from "@/hooks/use-s3-jobs";
import { formatRelative } from "@/lib/format";
import type { S3JobStatus } from "@/types/bigrag";
import { S3JobForm } from "./components/s3-job-form";

const statusVariant: Record<S3JobStatus, "success" | "warning" | "info" | "error" | "neutral"> = {
  complete: "success",
  ingesting: "info",
  listing: "info",
  pending: "warning",
  failed: "error",
};

const S3JobsTab = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);

  const { data, isPending } = useS3Jobs(name);
  const remove = useDeleteS3Job(name);
  const resync = useResyncS3Job(name);
  const [showForm, setShowForm] = useState(false);
  const [deleteJob, setDeleteJob] = useState<{ id: string; bucket: string } | null>(null);

  const jobs = data?.jobs ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-medium">S3 ingestion jobs</h2>
          <p className="text-xs text-muted-foreground">
            Scan an S3 bucket and ingest every supported file under the prefix.
          </p>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="size-4" /> Ingest from S3
        </Button>
      </div>

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : jobs.length === 0 ? (
        <Empty
          icon={<Cloud className="size-6" />}
          title="No S3 jobs yet"
          description="Start an ingestion to pull documents from an S3 or S3-compatible bucket into this collection."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="grid grid-cols-[2fr_auto_auto_auto_auto_auto] gap-4 border-b border-border px-4 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            <span>Source</span>
            <span className="text-right">Found</span>
            <span className="text-right">Ingested</span>
            <span className="text-right">Skipped</span>
            <span className="text-right">Updated</span>
            <span className="w-[88px]" />
          </div>
          <ul className="divide-y divide-border">
            {jobs.map((j) => (
              <li
                key={j.id}
                className="grid grid-cols-[2fr_auto_auto_auto_auto_auto] items-center gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-mono text-sm">
                      s3:
                      {j.prefix ? `/${j.prefix}` : ""}
                    </span>
                    <Badge dot variant={statusVariant[j.status]}>
                      {j.status}
                    </Badge>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{j.region}</span>
                    {j.endpoint_url && <span>· {new URL(j.endpoint_url).host}</span>}
                    {j.file_types.length > 0 && (
                      <span>· {j.file_types.map((t) => `.${t}`).join(", ")}</span>
                    )}
                  </div>
                  {j.error_message && (
                    <div className="mt-1 truncate text-xs text-destructive">{j.error_message}</div>
                  )}
                </div>
                <span className="text-right text-sm tabular-nums text-muted-foreground">
                  {j.total_found}
                </span>
                <span className="text-right text-sm tabular-nums text-muted-foreground">
                  {j.total_ingested}
                </span>
                <span className="text-right text-sm tabular-nums text-muted-foreground">
                  {j.total_skipped}
                </span>
                <span className="text-right text-sm text-muted-foreground">
                  {formatRelative(j.updated_at)}
                </span>
                <div className="flex items-center justify-end gap-1">
                  <Button
                    aria-label="Resync"
                    disabled={resync.isPending}
                    onClick={async () => {
                      try {
                        await resync.mutateAsync(j.id);
                      } catch (err) {
                        toast.error(err instanceof Error ? err.message : "Resync failed");
                      }
                    }}
                    size="icon"
                    variant="ghost"
                  >
                    <RefreshCw className="size-4" />
                  </Button>
                  <Button
                    aria-label="Delete"
                    onClick={() => setDeleteJob({ id: j.id, bucket: j.bucket })}
                    size="icon"
                    variant="ghost"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <S3JobForm collection={name} onClose={() => setShowForm(false)} open={showForm} />

      <ConfirmDialog
        confirmLabel="Delete"
        description={
          deleteJob
            ? `Delete the S3 job for "${deleteJob.bucket}"? This stops any in-flight listing and removes the job record. Already-ingested documents stay in the collection.`
            : ""
        }
        loading={remove.isPending}
        onClose={() => setDeleteJob(null)}
        onConfirm={async () => {
          if (!deleteJob) return;
          try {
            await remove.mutateAsync(deleteJob.id);
            setDeleteJob(null);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Delete failed");
          }
        }}
        open={!!deleteJob}
        title="Delete S3 job"
      />
    </div>
  );
};

export default S3JobsTab;
