import { Archive, CheckCircle2, CloudUpload, DatabaseBackup, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { useBackups, useStartBackup } from "@/hooks/use-backups";
import { useInstanceSettings } from "@/hooks/use-instance-settings";
import { formatBytes, formatRelative } from "@/lib/format";
import type { BackupJob } from "@/types/bigrag";
import { InstanceSettingsTab } from "./instance-settings-tab";

export const BackupsTab = () => {
  const backups = useBackups();
  const settings = useInstanceSettings();
  const startBackup = useStartBackup();
  const [label, setLabel] = useState("");
  const jobs = backups.data?.jobs ?? [];
  const active = jobs.some((job) => job.status === "pending" || job.status === "running");
  const destinationConfigured = Boolean(settings.data?.values.backup_s3_bucket?.value);

  return (
    <div className="flex flex-col gap-4">
      <BackupGuide
        active={active}
        destinationConfigured={destinationConfigured}
        streaming={backups.streaming}
      />
      <InstanceSettingsTab group="backups" />
      <Card className="rounded-md">
        <CardHeader className="border-b border-border bg-muted/35 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <DatabaseBackup className="size-4" />
                Readable backups
              </CardTitle>
              <CardDescription>
                Export full-instance JSON, JSONL, vectors, and raw uploaded files to S3-compatible
                storage.
              </CardDescription>
            </div>
            <Badge variant={backups.streaming ? "success" : "neutral"} dot>
              {backups.streaming ? "live" : "polling"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-5 p-4">
          <div className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
            <div className="flex items-start gap-2">
              <ShieldAlert className="mt-0.5 size-4 shrink-0" />
              <p>
                Backups are readable and not client-side encrypted. Treat the destination bucket as
                sensitive because it contains document content, vectors, chats, logs, and decrypted
                provider settings.
              </p>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
            <Input
              label="Backup label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="Before model migration"
              description="Optional label shown in the backup history."
            />
            <div className="flex items-end">
              <Button
                className="w-full lg:w-auto"
                disabled={startBackup.isPending || active}
                onClick={() => startBackup.mutate({ label })}
              >
                <CloudUpload className="size-4" />
                {active ? "Backup running" : "Start backup"}
              </Button>
            </div>
          </div>
          {jobs.length ? <BackupJobs jobs={jobs} /> : <EmptyBackups />}
        </CardContent>
      </Card>
    </div>
  );
};

const BackupGuide = ({
  active,
  destinationConfigured,
  streaming,
}: {
  active: boolean;
  destinationConfigured: boolean;
  streaming: boolean;
}) => (
  <section className="rounded-md border border-border bg-card p-4">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Backup runbook
        </div>
        <h3 className="mt-1 text-base font-semibold">Set up, validate, export</h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
          Backups stay readable, so configure a dedicated bucket, test the destination, then run
          exports from the history panel below.
        </p>
      </div>
      <Badge variant={streaming ? "success" : "neutral"} dot>
        {streaming ? "live updates" : "polling"}
      </Badge>
    </div>
    <div className="mt-4 grid gap-3 md:grid-cols-3">
      <BackupStep
        complete={destinationConfigured}
        label="Destination"
        value={destinationConfigured ? "Bucket selected" : "Bucket required"}
      />
      <BackupStep
        complete={destinationConfigured}
        label="Validation"
        value={destinationConfigured ? "Ready to test" : "Waiting for destination"}
      />
      <BackupStep
        complete={!active}
        label="Export"
        value={active ? "Backup running" : "Ready when validated"}
      />
    </div>
  </section>
);

const BackupStep = ({
  complete,
  label,
  value,
}: {
  complete: boolean;
  label: string;
  value: string;
}) => (
  <div className="rounded-md border border-border bg-background p-3">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      <CheckCircle2 className={complete ? "size-4 text-success" : "size-4 text-muted-foreground"} />
      {label}
    </div>
    <div className="mt-2 text-sm font-semibold">{value}</div>
  </div>
);

const EmptyBackups = () => (
  <Empty
    icon={<Archive className="size-5" />}
    title="No backups yet"
    description="Configure a backup bucket, test the destination, then start the first readable export."
    bordered={false}
    className="rounded-md border border-dashed border-border bg-muted/40"
  />
);

const BackupJobs = ({ jobs }: { jobs: BackupJob[] }) => (
  <div className="overflow-hidden rounded-md border border-border">
    <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-border bg-muted/60 px-4 py-2 text-xs font-semibold text-muted-foreground">
      <span>Backup</span>
      <span>Size</span>
      <span>Status</span>
    </div>
    <div className="divide-y divide-border">
      {jobs.map((job) => (
        <BackupJobRow key={job.id} job={job} />
      ))}
    </div>
  </div>
);

const BackupJobRow = ({ job }: { job: BackupJob }) => (
  <div className="grid gap-3 px-4 py-3 md:grid-cols-[1fr_auto_auto] md:items-center">
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <div className="truncate text-sm font-semibold">{job.label || job.id}</div>
        <span className="text-xs text-muted-foreground">{formatRelative(job.created_at)}</span>
      </div>
      <div className="mt-1 truncate text-xs text-muted-foreground">
        {job.destination_prefix || "Destination pending"}
      </div>
      {job.error_message && (
        <div className="mt-1 text-xs text-destructive">{job.error_message}</div>
      )}
      {(job.status === "pending" || job.status === "running") && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${Math.max(4, Math.round(job.progress * 100))}%` }}
          />
        </div>
      )}
    </div>
    <div className="text-sm text-muted-foreground">
      {formatBytes(job.byte_count)} · {job.object_count} objects
    </div>
    <Badge variant={statusVariant(job.status)} dot>
      {job.status}
    </Badge>
  </div>
);

const statusVariant = (status: BackupJob["status"]) => {
  if (status === "succeeded") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "primary";
  return "neutral";
};
