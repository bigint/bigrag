import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/page-header";
import { WebhookForm } from "@/features/webhooks/webhook-form";
import { WebhookList } from "@/features/webhooks/webhook-list";
import { WebhookSecretModal } from "@/features/webhooks/webhook-secret-modal";
import { useDeleteWebhook, useTestWebhook, useWebhooks } from "@/hooks/use-webhooks";

export const Route = createFileRoute("/_dashboard/webhooks")({
  component: () => <WebhooksPage />,
});

const WebhooksPage = () => {
  const { data, isPending, error } = useWebhooks();
  const remove = useDeleteWebhook();
  const test = useTestWebhook();

  const [formOpen, setFormOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [newSecret, setNewSecret] = useState<string | null>(null);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await remove.mutateAsync(deleteId);
      setDeleteId(null);
    } catch {}
  };

  return (
    <div>
      <PageHeader
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="size-4" /> Add Webhook
          </Button>
        }
        description="Receive real-time collection event notifications."
        title="Webhooks"
      />

      {error && (
        <div
          className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
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
    </div>
  );
};
