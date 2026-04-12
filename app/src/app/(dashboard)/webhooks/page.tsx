"use client";

import { Plus, Send, Trash2, Webhook } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateWebhook,
  useDeleteWebhook,
  useTestWebhook,
  useWebhooks,
} from "@/hooks/use-webhooks";

const EVENTS = [
  "document.ingested",
  "document.failed",
  "collection.created",
  "collection.deleted",
  "s3.job.completed",
];

const WebhooksPage = () => {
  const { data, isPending } = useWebhooks();
  const create = useCreateWebhook();
  const remove = useDeleteWebhook();
  const test = useTestWebhook();

  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(EVENTS));
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const w = await create.mutateAsync({
        url,
        events: Array.from(selected),
        description,
      });
      setCreatedSecret(w.secret);
      setUrl("");
      setDescription("");
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Webhooks"
        description="Receive HTTP callbacks when documents ingest, fail, or collections change."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New webhook
          </Button>
        }
      />

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : data?.webhooks.length === 0 ? (
        <Empty icon={Webhook} title="No webhooks yet" />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {data?.webhooks.map((w) => (
                <li
                  key={w.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-sm">{w.url}</span>
                      {w.active ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="warning">paused</Badge>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
                      {w.events.map((e) => (
                        <span
                          key={e}
                          className="rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground"
                        >
                          {e}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="ghost" onClick={() => test.mutate(w.id)}>
                      <Send className="h-4 w-4" /> Test
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        if (!confirm(`Delete webhook ${w.url}?`)) return;
                        await remove.mutateAsync(w.id);
                      }}
                      aria-label="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title="New webhook" description="Subscribe to events from every collection.">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Input
              label="URL"
              type="url"
              placeholder="https://..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
            <Textarea
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <div>
              <div className="mb-1.5 text-xs font-medium">Events</div>
              <div className="flex flex-wrap gap-2">
                {EVENTS.map((evt) => {
                  const active = selected.has(evt);
                  return (
                    <button
                      key={evt}
                      type="button"
                      onClick={() =>
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (next.has(evt)) next.delete(evt);
                          else next.add(evt);
                          return next;
                        })
                      }
                      className={
                        active
                          ? "rounded-full border border-primary bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
                          : "rounded-full border border-border bg-card px-3 py-1 text-xs text-foreground hover:bg-accent"
                      }
                    >
                      {evt}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <DialogClose
                render={
                  <Button variant="ghost" type="button">
                    Cancel
                  </Button>
                }
              />
              <Button type="submit" disabled={create.isPending || selected.size === 0}>
                {create.isPending ? "Creating…" : "Create webhook"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!createdSecret} onOpenChange={(o) => !o && setCreatedSecret(null)}>
        <DialogContent title="Signing secret" description="Store this to verify HMAC signatures.">
          {createdSecret && (
            <div className="flex flex-col gap-3">
              <div className="break-all rounded-md border border-border bg-muted p-3 font-mono text-xs">
                {createdSecret}
              </div>
              <Button
                onClick={() => {
                  navigator.clipboard.writeText(createdSecret);
                  toast.success("Copied");
                }}
              >
                Copy secret
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WebhooksPage;
