"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api";

type GdprResponse = {
  user_id: string;
  deleted_sessions: number;
  deleted_api_keys: number;
  deleted_collections: number;
  deleted_documents: number;
  deleted_at: string;
  certificate: string;
};

export const GdprTab = () => {
  const [userId, setUserId] = useState("");
  const [confirm, setConfirm] = useState("");
  const [last, setLast] = useState<GdprResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<GdprResponse>(`v1/admin/users/${encodeURIComponent(id)}/gdpr`),
    onSuccess: (res) => {
      setLast(res);
      setUserId("");
      setConfirm("");
      toast.success("GDPR erasure complete");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed");
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;
    if (confirm !== "DELETE") {
      toast.error("Type DELETE to confirm");
      return;
    }
    mutation.mutate(userId);
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>GDPR erasure</CardTitle>
          <CardDescription>
            Cascade-delete a user's sessions, API keys, and tombstones the user row
            (email → deleted-{"{id}"}@tombstone.local). Returns a sha256 certificate so
            legal can prove erasure. This is irreversible.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex max-w-md flex-col gap-3">
            <Input
              label="User ID (UUID)"
              placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
            />
            <Input
              label='Type "DELETE" to confirm'
              placeholder="DELETE"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
            <div className="flex justify-end">
              <Button
                type="submit"
                variant="destructive"
                disabled={mutation.isPending || !userId || confirm !== "DELETE"}
              >
                {mutation.isPending ? "Deleting…" : "Erase user data"}
              </Button>
            </div>
          </form>

          {last && (
            <div className="mt-6 rounded-md border border-success/40 bg-success/5 p-4 text-sm">
              <div className="mb-2 font-medium text-success">Erasure certificate</div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <dt className="text-muted-foreground">User ID</dt>
                <dd className="font-mono text-foreground">{last.user_id}</dd>
                <dt className="text-muted-foreground">Sessions deleted</dt>
                <dd className="font-mono text-foreground">{last.deleted_sessions}</dd>
                <dt className="text-muted-foreground">API keys deleted</dt>
                <dd className="font-mono text-foreground">{last.deleted_api_keys}</dd>
                <dt className="text-muted-foreground">Timestamp</dt>
                <dd className="font-mono text-foreground">{last.deleted_at}</dd>
                <dt className="text-muted-foreground">Certificate (sha256)</dt>
                <dd className="break-all font-mono text-[10px] text-foreground">
                  {last.certificate}
                </dd>
              </dl>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
