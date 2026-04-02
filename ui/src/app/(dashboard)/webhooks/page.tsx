"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { CreateWebhookBody } from "@bigrag/client";
import { getClient } from "@/lib/client";
import { webhooksQueryOptions, webhookDeliveriesQueryOptions } from "@/lib/queries";
import { timeAgo } from "@/lib/utils";

const EVENTS = ["document.ready", "document.failed", "document.processing"] as const;

const WebhooksPage = () => {
  const queryClient = useQueryClient();
  const webhooksQuery = useQuery(webhooksQueryOptions());
  const webhooks = webhooksQuery.data?.webhooks ?? [];

  const [isCreating, setIsCreating] = useState(false);
  const [url, setUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<Set<string>>(new Set(["document.ready", "document.failed"]));
  const [collections, setCollections] = useState("");
  const [description, setDescription] = useState("");
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (body: CreateWebhookBody) => getClient().createWebhook(body),
    onSuccess: (res) => {
      setCreatedSecret(res.secret);
      setUrl("");
      setSelectedEvents(new Set(["document.ready", "document.failed"]));
      setCollections("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => getClient().deleteWebhook(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhooks"] })
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      getClient().updateWebhook(id, { active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhooks"] })
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => getClient().testWebhook(id)
  });

  const handleCreate = () => {
    if (!url.trim() || selectedEvents.size === 0) return;
    const body: CreateWebhookBody = {
      url: url.trim(),
      events: [...selectedEvents],
      description: description.trim() || undefined,
    };
    if (collections.trim()) {
      body.collections = collections.split(",").map((s) => s.trim()).filter(Boolean);
    }
    createMutation.mutate(body);
  };

  const toggleEvent = (event: string) => {
    const next = new Set(selectedEvents);
    if (next.has(event)) next.delete(event);
    else next.add(event);
    setSelectedEvents(next);
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text">Webhooks</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Receive push notifications when documents finish processing
          </p>
        </div>
        <button
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
          onClick={() => { setIsCreating(!isCreating); setCreatedSecret(null); }}
          type="button"
        >
          {isCreating ? "Cancel" : "Add Webhook"}
        </button>
      </div>

      {/* Create form */}
      {isCreating && (
        <div className="mb-6 rounded-lg border border-border bg-bg-card p-5">
          <h3 className="mb-4 text-sm font-medium text-text">Register Webhook</h3>

          {createdSecret && (
            <div className="mb-4 rounded-lg border border-success/30 bg-success/5 p-4">
              <p className="mb-2 text-sm font-medium text-success">
                Webhook created. Copy the signing secret — it won't be shown again.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded bg-bg-hover px-3 py-2 font-mono text-sm text-text">
                  {createdSecret}
                </code>
                <button
                  className="rounded-md bg-bg-hover px-3 py-2 text-sm text-text-muted transition-colors hover:text-text"
                  onClick={() => handleCopy(createdSecret)}
                  type="button"
                >
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs text-text-muted">URL</label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/webhook"
                type="url"
                value={url}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Events</label>
              <div className="flex flex-wrap gap-2">
                {EVENTS.map((event) => (
                  <button
                    className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                      selectedEvents.has(event)
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-border bg-bg-input text-text-muted hover:border-border-hover"
                    }`}
                    key={event}
                    onClick={() => toggleEvent(event)}
                    type="button"
                  >
                    {event}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">
                Collections (comma-separated, leave empty for all)
              </label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setCollections(e.target.value)}
                placeholder="docs, reports"
                type="text"
                value={collections}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Description</label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                type="text"
                value={description}
              />
            </div>
            <button
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
              disabled={!url.trim() || selectedEvents.size === 0 || createMutation.isPending}
              onClick={handleCreate}
              type="button"
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </button>
            {createMutation.error && (
              <p className="text-xs text-danger">{createMutation.error.message}</p>
            )}
          </div>
        </div>
      )}

      {/* Loading */}
      {webhooksQuery.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div className="h-20 animate-pulse rounded-lg border border-border bg-bg-card" key={i} />
          ))}
        </div>
      )}

      {webhooksQuery.error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {webhooksQuery.error.message}
        </div>
      )}

      {!webhooksQuery.isLoading && !webhooksQuery.error && webhooks.length === 0 && (
        <div className="py-16 text-center text-sm text-text-dim">
          No webhooks registered. Add one to get started.
        </div>
      )}

      {/* Webhooks table */}
      {webhooks.length > 0 && (
        <div className="space-y-3">
          {webhooks.map((wh) => (
            <div className="rounded-lg border border-border bg-bg-card" key={wh.id}>
              <div className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block size-2 rounded-full ${wh.active ? "bg-success" : "bg-text-dim"}`} />
                    <span className="truncate font-mono text-sm text-text">{wh.url}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {wh.events.map((e) => (
                      <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent" key={e}>
                        {e}
                      </span>
                    ))}
                    {wh.collections && (
                      <span className="text-[11px] text-text-dim">
                        collections: {wh.collections.join(", ")}
                      </span>
                    )}
                    {wh.description && (
                      <span className="text-[11px] text-text-dim">— {wh.description}</span>
                    )}
                  </div>
                </div>
                <div className="ml-4 flex shrink-0 items-center gap-2">
                  <button
                    className="rounded-md px-2.5 py-1 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-text"
                    onClick={() => setExpandedId(expandedId === wh.id ? null : wh.id)}
                    type="button"
                  >
                    Deliveries
                  </button>
                  <button
                    className="rounded-md px-2.5 py-1 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
                    disabled={testMutation.isPending}
                    onClick={() => testMutation.mutate(wh.id)}
                    type="button"
                  >
                    Test
                  </button>
                  <button
                    className="rounded-md px-2.5 py-1 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-text"
                    onClick={() => toggleMutation.mutate({ id: wh.id, active: !wh.active })}
                    type="button"
                  >
                    {wh.active ? "Disable" : "Enable"}
                  </button>
                  <button
                    className="rounded-md px-2.5 py-1 text-xs font-medium text-danger transition-colors hover:bg-danger/10"
                    onClick={() => {
                      if (confirm("Delete this webhook?")) deleteMutation.mutate(wh.id);
                    }}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Test result inline */}
              {testMutation.isSuccess && testMutation.variables === wh.id && (
                <div className={`mx-4 mb-3 rounded-md px-3 py-2 text-xs ${
                  testMutation.data.status === "delivered"
                    ? "bg-success/10 text-success"
                    : "bg-danger/10 text-danger"
                }`}>
                  Test: {testMutation.data.status}
                  {testMutation.data.status_code && ` (HTTP ${testMutation.data.status_code})`}
                  {testMutation.data.error && ` — ${testMutation.data.error}`}
                </div>
              )}

              {/* Delivery history */}
              {expandedId === wh.id && <DeliveryHistory webhookId={wh.id} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const DeliveryHistory = ({ webhookId }: { readonly webhookId: string }) => {
  const query = useQuery(webhookDeliveriesQueryOptions(webhookId));
  const deliveries = query.data?.deliveries ?? [];

  if (query.isLoading) {
    return <div className="px-4 pb-3 text-xs text-text-dim">Loading deliveries...</div>;
  }

  if (deliveries.length === 0) {
    return <div className="px-4 pb-3 text-xs text-text-dim">No deliveries yet</div>;
  }

  return (
    <div className="border-t border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-bg-hover/50">
            <th className="px-4 py-2 text-left font-medium text-text-dim">Event</th>
            <th className="px-4 py-2 text-left font-medium text-text-dim">Status</th>
            <th className="px-4 py-2 text-left font-medium text-text-dim">Attempts</th>
            <th className="px-4 py-2 text-left font-medium text-text-dim">HTTP</th>
            <th className="px-4 py-2 text-left font-medium text-text-dim">Error</th>
            <th className="px-4 py-2 text-left font-medium text-text-dim">Time</th>
          </tr>
        </thead>
        <tbody>
          {deliveries.map((d) => (
            <tr className="border-t border-border/50" key={d.id}>
              <td className="px-4 py-2 font-mono text-text-muted">{d.event}</td>
              <td className="px-4 py-2">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  d.status === "delivered"
                    ? "bg-success/10 text-success"
                    : d.status === "failed"
                      ? "bg-danger/10 text-danger"
                      : "bg-warning/10 text-warning"
                }`}>
                  {d.status}
                </span>
              </td>
              <td className="px-4 py-2 text-text-dim">{d.attempts}</td>
              <td className="px-4 py-2 font-mono text-text-dim">{d.last_status_code ?? "—"}</td>
              <td className="max-w-48 truncate px-4 py-2 text-text-dim">{d.last_error ?? "—"}</td>
              <td className="px-4 py-2 text-text-dim">{d.created_at ? timeAgo(d.created_at) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default WebhooksPage;
