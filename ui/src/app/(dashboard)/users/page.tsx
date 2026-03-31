"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Trash2 } from "lucide-react";
import { useState } from "react";
import {
  createInvite,
  deleteInvite,
  deleteUser,
  listInvites,
  listUsers,
  updateUserRole
} from "@/lib/api";
import { getUser } from "@/lib/auth-store";

const Pulse = ({ className }: { readonly className?: string }) => (
  <div className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`} />
);

const UsersPage = () => {
  const queryClient = useQueryClient();
  const currentUser = getUser();

  const usersQuery = useQuery({
    queryFn: () => listUsers(),
    queryKey: ["users"]
  });

  const invitesQuery = useQuery({
    queryFn: () => listInvites(),
    queryKey: ["invites"]
  });

  const [inviteRole, setInviteRole] = useState<"member" | "admin">("member");
  const [inviteLink, setInviteLink] = useState("");
  const [copied, setCopied] = useState(false);

  const createInviteMutation = useMutation({
    mutationFn: () => createInvite({ role: inviteRole }),
    onSuccess: (data) => {
      const link = `${window.location.origin}/signup?code=${data.code}`;
      setInviteLink(link);
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    }
  });

  const deleteInviteMutation = useMutation({
    mutationFn: (id: string) => deleteInvite(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    }
  });

  const deleteUserMutation = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    }
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      updateUserRole(id, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    }
  });

  const handleCopy = async () => {
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const users = usersQuery.data?.users ?? [];
  const invites = invitesQuery.data?.invites ?? [];
  const pendingInvites = invites.filter((inv) => !inv.used_by);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-US", {
      day: "numeric",
      month: "short",
      year: "numeric"
    });

  return (
    <div className="text-text">
      <div className="mx-auto max-w-5xl px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Manage members and invite links
          </p>
        </div>

        {/* Section 1: Invite */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Invite
          </h2>
          <div className="rounded-lg border border-border bg-bg-card p-5">
            <div className="flex items-center gap-3">
              <select
                className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
                onChange={(e) =>
                  setInviteRole(e.target.value as "member" | "admin")
                }
                value={inviteRole}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
              <button
                className="rounded-md bg-text px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:opacity-50"
                disabled={createInviteMutation.isPending}
                onClick={() => createInviteMutation.mutate()}
                type="button"
              >
                {createInviteMutation.isPending
                  ? "Creating…"
                  : "Create invite link"}
              </button>
            </div>

            {createInviteMutation.isError && (
              <div className="mt-3 rounded-md border border-danger/20 bg-danger/10 px-3 py-2.5 text-sm text-danger">
                {createInviteMutation.error?.message ??
                  "Failed to create invite"}
              </div>
            )}

            {inviteLink && (
              <div className="mt-4 flex items-center gap-2 rounded-md border border-border bg-bg px-3 py-2">
                <span className="flex-1 truncate font-mono text-xs text-text-muted">
                  {inviteLink}
                </span>
                <button
                  className="shrink-0 rounded p-1 text-text-muted transition-colors hover:text-text"
                  onClick={handleCopy}
                  type="button"
                >
                  {copied ? (
                    <Check className="size-4 text-success" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Section 2: Members */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Members
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            {usersQuery.isLoading ? (
              <div className="divide-y divide-border">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div className="flex items-center gap-4 px-5 py-3.5" key={i}>
                    <Pulse className="h-4 w-32" />
                    <Pulse className="h-4 w-40" />
                    <Pulse className="ml-auto h-4 w-20" />
                    <Pulse className="h-4 w-16" />
                  </div>
                ))}
              </div>
            ) : users.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-text-dim">
                No members found.
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border text-left text-[13px] text-text-dim">
                    <th className="px-5 py-3 font-medium">Name</th>
                    <th className="px-5 py-3 font-medium">Email</th>
                    <th className="px-5 py-3 font-medium">Role</th>
                    <th className="px-5 py-3 font-medium">Joined</th>
                    <th className="px-5 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((u) => {
                    const isSelf = u.id === currentUser?.id;
                    return (
                      <tr key={u.id}>
                        <td className="px-5 py-3.5 text-sm text-text">
                          {u.display_name}
                          {isSelf && (
                            <span className="ml-2 text-xs text-text-dim">
                              (you)
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 font-mono text-sm text-text-muted">
                          {u.email}
                        </td>
                        <td className="px-5 py-3.5">
                          {isSelf ? (
                            <span className="text-sm capitalize text-text-muted">
                              {u.role}
                            </span>
                          ) : (
                            <select
                              className="rounded-md border border-border bg-bg px-2 py-1 text-sm text-text outline-none focus:border-text-muted"
                              defaultValue={u.role}
                              disabled={updateRoleMutation.isPending}
                              onChange={(e) =>
                                updateRoleMutation.mutate({
                                  id: u.id,
                                  role: e.target.value
                                })
                              }
                            >
                              <option value="member">member</option>
                              <option value="admin">admin</option>
                            </select>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-sm text-text-muted">
                          {formatDate(u.created_at)}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          {!isSelf && (
                            <button
                              className="rounded p-1 text-text-dim transition-colors hover:text-danger disabled:opacity-50"
                              disabled={deleteUserMutation.isPending}
                              onClick={() => deleteUserMutation.mutate(u.id)}
                              type="button"
                            >
                              <Trash2 className="size-4" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Section 3: Pending Invites */}
        {(invitesQuery.isLoading || pendingInvites.length > 0) && (
          <div>
            <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
              Pending Invites
            </h2>
            <div className="rounded-lg border border-border bg-bg-card">
              {invitesQuery.isLoading ? (
                <div className="divide-y divide-border">
                  {Array.from({ length: 2 }).map((_, i) => (
                    <div
                      className="flex items-center gap-4 px-5 py-3.5"
                      key={i}
                    >
                      <Pulse className="h-4 w-16" />
                      <Pulse className="h-4 w-32" />
                      <Pulse className="ml-auto h-4 w-24" />
                    </div>
                  ))}
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border text-left text-[13px] text-text-dim">
                      <th className="px-5 py-3 font-medium">Role</th>
                      <th className="px-5 py-3 font-medium">Created by</th>
                      <th className="px-5 py-3 font-medium">Expires</th>
                      <th className="px-5 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {pendingInvites.map((inv) => (
                      <tr key={inv.id}>
                        <td className="px-5 py-3.5 text-sm capitalize text-text">
                          {inv.role}
                        </td>
                        <td className="px-5 py-3.5 font-mono text-sm text-text-muted">
                          {inv.created_by_email}
                        </td>
                        <td className="px-5 py-3.5 text-sm text-text-muted">
                          {formatDate(inv.expires_at)}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button
                            className="rounded p-1 text-text-dim transition-colors hover:text-danger disabled:opacity-50"
                            disabled={deleteInviteMutation.isPending}
                            onClick={() => deleteInviteMutation.mutate(inv.id)}
                            type="button"
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UsersPage;
