"use client";

import { Plus, Trash2, UserRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { useSession } from "@/hooks/use-auth";
import { useCreateUser, useDeleteUser, useUpdateUser, useUsers } from "@/hooks/use-users";
import { formatRelative } from "@/lib/format";

const initialsOf = (name: string, email: string) => {
  const source = name?.trim() || email || "?";
  const [first, second] = source.split(/\s+/).filter(Boolean);
  if (first && second) return `${first[0]}${second[0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
};

const UsersPage = () => {
  const { data: session } = useSession();
  const { data, isPending } = useUsers();
  const create = useCreateUser();
  const update = useUpdateUser();
  const remove = useDeleteUser();

  const [addOpen, setAddOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const [resetForUser, setResetForUser] = useState<{ id: string; email: string } | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [deleteFor, setDeleteFor] = useState<{ id: string; email: string } | null>(null);

  const closeReset = () => {
    setResetForUser(null);
    setNewPassword("");
  };

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await create.mutateAsync({ email, password, display_name: displayName });
      setEmail("");
      setPassword("");
      setDisplayName("");
      setAddOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const resetPassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!resetForUser) return;
    try {
      await update.mutateAsync({ id: resetForUser.id, password: newPassword });
      toast.success("Password reset — user will need to sign in again");
      closeReset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div>
      <PageHeader
        title="Admins"
        description="Every admin has full access — including creating and revoking API keys."
        actions={
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="size-4" /> Add admin
          </Button>
        }
      />

      {isPending ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : data?.users.length === 0 ? (
        <Empty icon={<UserRound className="size-6" />} title="No admins" />
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
                    <div className="flex size-9 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                      {initialsOf(u.display_name, u.email)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{u.display_name || "—"}</span>
                        <Badge variant={u.role === "admin" ? "primary" : "neutral"}>{u.role}</Badge>
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
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setResetForUser({ id: u.id, email: u.email })}
                        >
                          Reset password
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label="Delete"
                          className="hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => setDeleteFor({ id: u.id, email: u.email })}
                        >
                          <Trash2 className="size-4" />
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

      <Modal onClose={() => setAddOpen(false)} open={addOpen} title="Invite an admin">
        <p className="mb-4 text-sm text-muted-foreground">
          They'll sign in with the password you set.
        </p>
        <form onSubmit={submit} className="space-y-4">
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
            description="At least 8 characters."
          />
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Invite admin"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal onClose={closeReset} open={!!resetForUser} title="Reset password">
        <p className="mb-4 text-sm text-muted-foreground">
          {resetForUser?.email} will be signed out everywhere and must sign in with the new
          password.
        </p>
        <form onSubmit={resetPassword} className="space-y-4">
          <Input
            label="New password"
            type="password"
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={closeReset}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Reset password"}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        confirmLabel="Delete"
        description={deleteFor ? `Remove ${deleteFor.email}? They'll lose access immediately.` : ""}
        loading={remove.isPending}
        onClose={() => setDeleteFor(null)}
        onConfirm={async () => {
          if (!deleteFor) return;
          try {
            await remove.mutateAsync(deleteFor.id);
            setDeleteFor(null);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed");
          }
        }}
        open={!!deleteFor}
        title="Remove admin"
      />
    </div>
  );
};

export default UsersPage;
