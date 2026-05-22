import { useForm } from "@tanstack/react-form";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import {
  defaultWebhookFormValues,
  toggleWebhookCategory,
  toggleWebhookEvent,
  validateWebhookFormValues,
  validateWebhookUrl,
  WEBHOOK_EVENT_CATEGORIES,
} from "@/features/webhooks/webhook-form-state";
import type { WorkerAvailability } from "@/features/workers/worker-status";
import { WorkerOfflineBanner } from "@/features/workers/worker-status-banner";
import { useCreateWebhook } from "@/hooks/use-webhooks";
import { errorText, firstString, submitWith } from "@/lib/form";

interface WebhookFormProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onCreated: (secret: string) => void;
  readonly workerAvailability: WorkerAvailability;
}

export const WebhookForm = ({ open, onClose, onCreated, workerAvailability }: WebhookFormProps) => {
  const create = useCreateWebhook();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm({
    defaultValues: defaultWebhookFormValues(),
    validators: {
      onSubmit: ({ value }) => validateWebhookFormValues(value),
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        const webhook = await create.mutateAsync({
          url: value.url.trim(),
          events: value.events,
        });
        onCreated(webhook.secret);
        reset();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Something went wrong";
        setSubmitError(message);
        toast.error(message);
      }
    },
  });

  const reset = () => {
    form.reset(defaultWebhookFormValues());
    setSubmitError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  return (
    <Modal onClose={handleClose} open={open} title="Add Webhook">
      <form
        className="space-y-4"
        noValidate
        onSubmit={submitWith(
          () => form.handleSubmit(),
          () => {
            setSubmitError(null);
          },
        )}
      >
        <WorkerOfflineBanner
          availability={workerAvailability}
          compact
          message="Document-event deliveries require bigrag-worker. Queued work will not run until the worker is started."
        />

        <form.Subscribe selector={(state) => state.errors}>
          {(errors) => {
            const formError = submitError ?? firstString(errors);
            return formError ? (
              <div
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                role="alert"
              >
                {formError}
              </div>
            ) : null;
          }}
        </form.Subscribe>

        <form.Field
          name="url"
          validators={{
            onBlur: ({ value }) => validateWebhookUrl(value),
            onSubmit: ({ value }) => validateWebhookUrl(value),
          }}
        >
          {(field) => (
            <Input
              autoComplete="off"
              description="We'll POST event payloads here with an HMAC signature."
              error={errorText(field.state.meta.errors)}
              id="webhook-url"
              label="URL"
              name={field.name}
              onBlur={field.handleBlur}
              onChange={(event) => field.handleChange(event.target.value)}
              placeholder="https://example.com/webhook"
              type="url"
              value={field.state.value}
            />
          )}
        </form.Field>

        <form.Field
          name="events"
          validators={{
            onSubmit: ({ value }) => (value.length === 0 ? "Select at least one event" : undefined),
          }}
        >
          {(field) => (
            <div className="space-y-1.5">
              <span className="text-sm font-medium">Events</span>
              <div className="max-h-60 space-y-3 overflow-y-auto rounded-md border border-border p-3">
                {Object.entries(WEBHOOK_EVENT_CATEGORIES).map(([category, events]) => {
                  const selected = field.state.value;
                  const allSelected = events.every((event) => selected.includes(event));
                  const someSelected =
                    !allSelected && events.some((event) => selected.includes(event));
                  return (
                    <div key={category}>
                      <Checkbox
                        aria-label={`Select all ${category} events`}
                        checked={allSelected}
                        className="text-sm font-medium"
                        id={`category-${category}`}
                        indeterminate={someSelected}
                        label={category}
                        onCheckedChange={() =>
                          field.handleChange(toggleWebhookCategory(selected, events))
                        }
                      />
                      <div className="ml-6 mt-1 space-y-1">
                        {events.map((event) => (
                          <Checkbox
                            aria-label={`Select ${event} event`}
                            checked={selected.includes(event)}
                            className="text-sm text-muted-foreground"
                            id={`event-${event}`}
                            key={event}
                            label={event}
                            onCheckedChange={() =>
                              field.handleChange(toggleWebhookEvent(selected, event))
                            }
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              {field.state.meta.errors.length > 0 && (
                <p className="text-xs text-destructive">{errorText(field.state.meta.errors)}</p>
              )}
            </div>
          )}
        </form.Field>

        <div className="flex justify-end gap-2 pt-1">
          <Button onClick={handleClose} type="button" variant="secondary">
            Cancel
          </Button>
          <Button disabled={create.isPending} type="submit">
            {create.isPending ? "Adding…" : "Add Webhook"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
