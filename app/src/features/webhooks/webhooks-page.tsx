import { Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Page } from "@/components/ui/page";
import { getWorkerAvailability } from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { usePlatformStats } from "@/hooks/use-platform";
import { useDeleteWebhook, useTestWebhook, useWebhooks } from "@/hooks/use-webhooks";
import { WebhookForm } from "./webhook-form";
import { WebhookList } from "./webhook-list";
import { WebhookSecretModal } from "./webhook-secret-modal";

export const WebhooksPage = () => {
  const { data, isPending, error } = useWebhooks();
  const { data: stats } = usePlatformStats();
  const remove = useDeleteWebhook();
  const test = useTestWebhook();

  const [formOpen, setFormOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const workerAvailability = getWorkerAvailability(stats);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await remove.mutateAsync(deleteId);
      setDeleteId(null);
    } catch {}
  };

  return (
    <Page.Shell>
      <Page.Header
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="size-4" /> Add Webhook
          </Button>
        }
        className="mb-0"
        description="Receive real-time data-operation notifications."
        title="Webhooks"
      />

      <WorkerOfflineBanner
        availability={workerAvailability}
        message="Data-operation deliveries require bigrag-worker. Queued work will not run until the worker is started."
      />

      {error && (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {error instanceof Error ? error.message : "Failed to load webhooks"}
        </div>
      )}

      <WebhookList
        loading={isPending}
        onAdd={() => setFormOpen(true)}
        onDelete={setDeleteId}
        onTest={(id) => test.mutate(id)}
        webhooks={data?.webhooks ?? []}
      />

      <WebhookForm
        onClose={() => setFormOpen(false)}
        onCreated={(secret) => {
          setFormOpen(false);
          setNewSecret(secret);
        }}
        open={formOpen}
        workerAvailability={workerAvailability}
      />

      <WebhookSecretModal onClose={() => setNewSecret(null)} secret={newSecret} />

      <ConfirmDialog
        confirmLabel="Delete"
        description="Are you sure you want to delete this webhook? This action cannot be undone."
        loading={remove.isPending}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        open={deleteId !== null}
        title="Delete Webhook"
      />
    </Page.Shell>
  );
};
