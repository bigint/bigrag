"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKeySummary,
  type CreateApiKeyRequest
} from "@/lib/api";
import { timeAgo } from "@/lib/utils";

const apiKeysQueryOptions = () => ({
  queryFn: () => listApiKeys(),
  queryKey: ["api-keys"]
});

const ApiKeysPage = () => {
  const queryClient = useQueryClient();
  const keysQuery = useQuery(apiKeysQueryOptions());
  const keys = keysQuery.data?.keys ?? [];

  const [isCreating, setIsCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyAdmin, setNewKeyAdmin] = useState(false);
  const [newKeyNamespaces, setNewKeyNamespaces] = useState("*");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const createMutation = useMutation({
    mutationFn: (body: CreateApiKeyRequest) => createApiKey(body),
    onSuccess: (res) => {
      setCreatedKey(res.key);
      setNewKeyName("");
      setNewKeyAdmin(false);
      setNewKeyNamespaces("*");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    }
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    }
  });

  const handleCreate = () => {
    if (!newKeyName.trim()) return;
    createMutation.mutate({
      admin: newKeyAdmin,
      name: newKeyName.trim(),
      namespaces: newKeyNamespaces
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    });
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
          <h1 className="text-xl font-semibold text-text">API Keys</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Manage API keys for authenticating with the bigRAG API
          </p>
        </div>
        <button
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
          onClick={() => {
            setIsCreating(!isCreating);
            setCreatedKey(null);
          }}
          type="button"
        >
          {isCreating ? "Cancel" : "Create Key"}
        </button>
      </div>

      {/* Create key form */}
      {isCreating && (
        <div className="mb-6 rounded-lg border border-border bg-bg-card p-5">
          <h3 className="mb-4 text-sm font-medium text-text">
            Create New API Key
          </h3>

          {createdKey && (
            <div className="mb-4 rounded-lg border border-success/30 bg-success/5 p-4">
              <p className="mb-2 text-sm font-medium text-success">
                API key created. Copy it now — it won't be shown again.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded bg-bg-hover px-3 py-2 font-mono text-sm text-text">
                  {createdKey}
                </code>
                <button
                  className="rounded-md bg-bg-hover px-3 py-2 text-sm text-text-muted transition-colors hover:text-text"
                  onClick={() => handleCopy(createdKey)}
                  type="button"
                >
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs text-text-muted">Name</label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="my-api-key"
                type="text"
                value={newKeyName}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">
                Namespaces (comma-separated, * for all)
              </label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setNewKeyNamespaces(e.target.value)}
                placeholder="*"
                type="text"
                value={newKeyNamespaces}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                checked={newKeyAdmin}
                id="admin-toggle"
                onChange={(e) => setNewKeyAdmin(e.target.checked)}
                type="checkbox"
              />
              <label
                className="text-sm text-text-muted"
                htmlFor="admin-toggle"
              >
                Admin privileges
              </label>
            </div>
            <button
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
              disabled={!newKeyName.trim() || createMutation.isPending}
              onClick={handleCreate}
              type="button"
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </button>
            {createMutation.error && (
              <p className="text-xs text-danger">
                {createMutation.error.message}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Keys list */}
      {keysQuery.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              className="h-20 animate-pulse rounded-lg border border-border bg-bg-card"
              key={i}
            />
          ))}
        </div>
      )}

      {keysQuery.error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {keysQuery.error.message}
        </div>
      )}

      {!keysQuery.isLoading && !keysQuery.error && keys.length === 0 && (
        <div className="py-16 text-center text-sm text-text-dim">
          No API keys found. Create one to get started.
        </div>
      )}

      {keys.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-bg-card">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                  Name
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                  Prefix
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                  Namespaces
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                  Admin
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                  Created
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                  Last Used
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-text-muted">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr
                  className="border-b border-border last:border-b-0 transition-colors hover:bg-bg-hover/50"
                  key={key.id}
                >
                  <td className="px-4 py-2.5 font-medium text-text">
                    {key.name}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-text-muted">
                    {key.prefix}...
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-text-muted">
                    {key.permissions.namespaces.join(", ")}
                  </td>
                  <td className="px-4 py-2.5">
                    {key.permissions.admin ? (
                      <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[11px] font-medium text-warning">
                        admin
                      </span>
                    ) : (
                      <span className="text-text-dim">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-text-muted">
                    {key.created_at ? timeAgo(key.created_at) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-text-muted">
                    {key.last_used_at ? timeAgo(key.last_used_at) : "Never"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      className="rounded-md px-3 py-1 text-xs font-medium text-danger transition-colors hover:bg-danger/10 disabled:opacity-50"
                      disabled={revokeMutation.isPending}
                      onClick={() => {
                        if (confirm(`Revoke key "${key.name}"?`)) {
                          revokeMutation.mutate(key.id);
                        }
                      }}
                      type="button"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ApiKeysPage;
