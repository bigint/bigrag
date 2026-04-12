"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import { useCreateWebhook } from "@/hooks/use-webhooks";

const EVENT_CATEGORIES: Record<string, string[]> = {
  Documents: ["document.ingested", "document.failed"],
  Collections: ["collection.created", "collection.deleted"],
  "S3 Jobs": ["s3.job.completed"],
};

interface WebhookFormProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onCreated: (secret: string) => void;
}

export const WebhookForm = ({ open, onClose, onCreated }: WebhookFormProps) => {
  const create = useCreateWebhook();
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(Object.values(EVENT_CATEGORIES).flat()),
  );
  const [formError, setFormError] = useState<string | null>(null);

  const toggleEvent = (event: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(event)) next.delete(event);
      else next.add(event);
      return next;
    });
  };

  const toggleCategory = (events: string[]) => {
    const allSelected = events.every((e) => selected.has(e));
    setSelected((prev) => {
      const next = new Set(prev);
      for (const e of events) {
        if (allSelected) next.delete(e);
        else next.add(e);
      }
      return next;
    });
  };

  const reset = () => {
    setUrl("");
    setDescription("");
    setSelected(new Set(Object.values(EVENT_CATEGORIES).flat()));
    setFormError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);
    if (!url.trim()) return setFormError("URL is required");
    try {
      new URL(url);
    } catch {
      return setFormError("Please enter a valid URL");
    }
    if (selected.size === 0) return setFormError("Select at least one event");

    try {
      const webhook = await create.mutateAsync({
        url: url.trim(),
        events: Array.from(selected),
        description,
      });
      onCreated(webhook.secret);
      reset();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setFormError(message);
      toast.error(message);
    }
  };

  return (
    <Modal onClose={handleClose} open={open} title="Add Webhook">
      <form className="space-y-4" onSubmit={handleSubmit}>
        {formError && (
          <div
            className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            role="alert"
          >
            {formError}
          </div>
        )}

        <Input
          autoComplete="off"
          description="We'll POST event payloads here with an HMAC signature."
          id="webhook-url"
          label="URL"
          name="url"
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/webhook"
          type="url"
          value={url}
        />

        <Textarea
          id="webhook-description"
          label="Description"
          name="description"
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional — a note for your team"
          value={description}
        />

        <div className="space-y-1.5">
          <span className="text-sm font-medium">Events</span>
          <div className="max-h-60 space-y-3 overflow-y-auto rounded-md border border-border p-3">
            {Object.entries(EVENT_CATEGORIES).map(([category, events]) => {
              const allSelected = events.every((e) => selected.has(e));
              const someSelected = !allSelected && events.some((e) => selected.has(e));
              return (
                <div key={category}>
                  <Checkbox
                    aria-label={`Select all ${category} events`}
                    checked={allSelected}
                    className="text-sm font-medium"
                    id={`category-${category}`}
                    indeterminate={someSelected}
                    label={category}
                    onCheckedChange={() => toggleCategory(events)}
                  />
                  <div className="ml-6 mt-1 space-y-1">
                    {events.map((event) => (
                      <Checkbox
                        aria-label={`Select ${event} event`}
                        checked={selected.has(event)}
                        className="text-sm text-muted-foreground"
                        id={`event-${event}`}
                        key={event}
                        label={event}
                        onCheckedChange={() => toggleEvent(event)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

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
