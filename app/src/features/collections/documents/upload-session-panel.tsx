import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Spinner } from "@/components/ui/spinner";
import { FileType } from "@/features/collections/documents/file-type";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";
import type { UploadSession } from "@/types/bigrag";

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

interface UploadSessionPanelProps {
  readonly loadingCancel: boolean;
  readonly onCancel: () => void;
  readonly onDismiss: () => void;
  readonly session: UploadSession;
  readonly streaming: boolean;
}

export const UploadSessionPanel = ({
  loadingCancel,
  onCancel,
  onDismiss,
  session,
  streaming,
}: UploadSessionPanelProps) => {
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

        <ProgressBar value={progressPct} />

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
