"use client";

import { Plus, Trash2, UserRound } from "lucide-react";
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
import { useSession } from "@/hooks/use-auth";
import { useCreateUser, useDeleteUser, useUpdateUser, useUsers } from "@/hooks/use-users";
import { formatRelative } from "@/lib/format";

const UsersPage = () => {
  const { data: session } = useSession();
  const { data, isPending } = useUsers();
  const create = useCreateUser();
  const update = useUpdateUser();
  const remove = useDeleteUser();

  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const [resetForUserId, setResetForUserId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await create.mutateAsync({ email, password, display_name: displayName });
      setEmail("");
      setPassword("");
      setDisplayName("");
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const resetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetForUserId) return;
    try {
      await update.mutateAsync({ id: resetForUserId, password: newPassword });
      toast.success("Password reset — user will need to sign in again");
      setResetForUserId(null);
      setNewPassword("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Admins"
        description="Every admin has full access — including the ability to create and revoke API keys."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> Add admin
          </Button>
        }
      />

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : data?.users.length === 0 ? (
        <Empty icon={UserRound} title="No admins" />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {data?.users.map((u) => (
                <li
                  key={u.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
                      {(u.display_name || u.email).slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{u.display_name || "—"}</span>
                        <Badge variant={u.role === "admin" ? "accent" : "neutral"}>{u.role}</Badge>
                        {u.id === session?.user.id && <Badge variant="info">you</Badge>}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {u.email} · last seen {formatRelative(u.last_login_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {u.id !== session?.user.id && (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => setResetForUserId(u.id)}>
                          Reset password
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            if (!confirm(`Remove ${u.email}?`)) return;
                            await remove.mutateAsync(u.id);
                          }}
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title="Invite an admin"
          description="They'll sign in with the password you set."
        >
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Input
              label="Display name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="Password"
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              description="The new admin should change this after signing in."
            />
            <div className="flex justify-end gap-2">
              <DialogClose
                render={
                  <Button variant="ghost" type="button">
                    Cancel
                  </Button>
                }
              />
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Invite admin"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!resetForUserId}
        onOpenChange={(o) => {
          if (!o) {
            setResetForUserId(null);
            setNewPassword("");
          }
        }}
      >
        <DialogContent
          title="Reset password"
          description="The user will be signed out everywhere and must sign in with the new password."
        >
          <form onSubmit={resetPassword} className="flex flex-col gap-4">
            <Input
              label="New password"
              type="password"
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <DialogClose
                render={
                  <Button variant="ghost" type="button">
                    Cancel
                  </Button>
                }
              />
              <Button type="submit" disabled={update.isPending}>
                {update.isPending ? "Saving…" : "Reset password"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersPage;
