"use client";

import { Check, Copy, KeyRound, Plus, Power, Trash2 } from "lucide-react";
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
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  useUpdateApiKey,
} from "@/hooks/use-api-keys";
import { formatRelative } from "@/lib/format";
import type { CreatedApiKey } from "@/types/bigrag";

const ApiKeysPage = () => {
  const { data, isPending } = useApiKeys();
  const create = useCreateApiKey();
  const toggle = useUpdateApiKey();
  const revoke = useDeleteApiKey();

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const created = await create.mutateAsync({ name });
      setNewKey(created);
      setName("");
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const copy = async () => {
    if (!newKey) return;
    await navigator.clipboard.writeText(newKey.key);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="API keys"
        description="Mint long-lived keys for external services. Keys start with bigrag_sk_ and are shown once."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New key
          </Button>
        }
      />

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : (data?.keys.length ?? 0) === 0 ? (
        <Empty
          icon={KeyRound}
          title="No API keys yet"
          description="Create one to let external services call the bigRAG API."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-[var(--color-border)]">
              {data?.keys.map((k) => (
                <li
                  key={k.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{k.name}</span>
                      {!k.active && <Badge variant="warning">revoked</Badge>}
                      {k.active && <Badge variant="success">active</Badge>}
                    </div>
                    <div className="mt-1 flex items-center gap-2 font-mono text-xs text-[var(--color-muted-foreground)]">
                      <span>{k.prefix}…</span>
                      <span className="opacity-40">·</span>
                      <span>
                        {k.last_used_at
                          ? `last used ${formatRelative(k.last_used_at)}`
                          : "never used"}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        toggle.mutate({ id: k.id, active: !k.active })
                      }
                      aria-label={k.active ? "Deactivate" : "Activate"}
                    >
                      <Power className="h-4 w-4" />
                      {k.active ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        if (!confirm(`Revoke key "${k.name}"? This cannot be undone.`)) return;
                        await revoke.mutateAsync(k.id);
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
        <DialogContent
          title="New API key"
          description="Give it a descriptive name — e.g. 'raven-production'."
        >
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Input
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              required
            />
            <div className="flex justify-end gap-2">
              <DialogClose render={<Button variant="ghost" type="button">Cancel</Button>} />
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create key"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!newKey} onOpenChange={(o) => !o && setNewKey(null)}>
        <DialogContent
          title="Save this key"
          description="This is the only time you'll see the full key. Copy it now."
        >
          {newKey && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-muted)] p-3 font-mono text-xs break-all">
                {newKey.key}
              </div>
              <Button onClick={copy} size="lg">
                {copied ? (
                  <>
                    <Check className="h-4 w-4" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" /> Copy key
                  </>
                )}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ApiKeysPage;
