"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getClient } from "@/lib/client";
import { getBaseUrl } from "@/lib/auth-store";
import { healthQueryOptions } from "@/lib/queries";

const Pulse = ({ className }: { readonly className?: string }) => (
  <div className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`} />
);

const SettingsPage = () => {
  const healthQuery = useQuery(healthQueryOptions());
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const passwordMutation = useMutation({
    mutationFn: () =>
      getClient().changePassword({
        current_password: currentPassword,
        new_password: newPassword
      }),
    onSuccess: () => {
      setPasswordMsg("Password changed successfully");
      setPasswordError("");
      setCurrentPassword("");
      setNewPassword("");
    },
    onError: (err) => {
      setPasswordError(err.message);
      setPasswordMsg("");
    }
  });

  const isConnected = healthQuery.isSuccess;
  const version = healthQuery.data?.version ?? "";

  return (
    <div className="text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Server connection and account settings
          </p>
        </div>

        {healthQuery.error && (
          <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {healthQuery.error.message}
          </div>
        )}

        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Connection
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            <div className="divide-y divide-border">
              <SettingsRow isLoading={false} label="API URL">
                <span className="font-mono text-sm text-text">
                  {getBaseUrl()}
                </span>
              </SettingsRow>

              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-text-muted">Status</span>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block size-2 rounded-full ${
                      isConnected ? "bg-success" : "bg-danger"
                    }`}
                  />
                  <span
                    className={`text-sm font-medium ${
                      isConnected ? "text-success" : "text-danger"
                    }`}
                  >
                    {isConnected ? "Connected" : "Disconnected"}
                  </span>
                </div>
              </div>

              <SettingsRow isLoading={healthQuery.isLoading} label="Version">
                <span className="font-mono text-sm text-text">
                  {version || "---"}
                </span>
              </SettingsRow>
            </div>
          </div>
        </div>

        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Change Password
          </h2>
          <div className="rounded-lg border border-border bg-bg-card p-5">
            <div className="max-w-md space-y-3">
              <div>
                <label className="mb-1 block text-xs text-text-muted">
                  Current Password
                </label>
                <input
                  className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                  type="password"
                  value={currentPassword}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-text-muted">
                  New Password
                </label>
                <input
                  className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password"
                  type="password"
                  value={newPassword}
                />
              </div>
              {passwordMsg && (
                <p className="text-sm text-success">{passwordMsg}</p>
              )}
              {passwordError && (
                <p className="text-sm text-danger">{passwordError}</p>
              )}
              <button
                className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
                disabled={
                  !currentPassword ||
                  !newPassword ||
                  passwordMutation.isPending
                }
                onClick={() => passwordMutation.mutate()}
                type="button"
              >
                {passwordMutation.isPending
                  ? "Changing..."
                  : "Change Password"}
              </button>
            </div>
          </div>
        </div>

        <div>
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            About
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            <div className="divide-y divide-border">
              <SettingsRow isLoading={false} label="Product">
                <span className="text-sm font-medium text-text">bigRAG</span>
              </SettingsRow>
              <SettingsRow isLoading={false} label="License">
                <span className="text-sm text-text">MIT</span>
              </SettingsRow>
              <SettingsRow isLoading={false} label="Docs">
                <a
                  className="font-mono text-sm text-accent hover:underline"
                  href={`${getBaseUrl()}/docs`}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {getBaseUrl()}/docs
                </a>
              </SettingsRow>
              <SettingsRow isLoading={false} label="Sponsor">
                <a
                  className="text-sm text-accent hover:underline"
                  href="https://github.com/sponsors/bigint"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  github.com/sponsors/bigint
                </a>
              </SettingsRow>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

interface SettingsRowProps {
  readonly label: string;
  readonly isLoading: boolean;
  readonly children: React.ReactNode;
}

const SettingsRow = ({ label, isLoading, children }: SettingsRowProps) => (
  <div className="flex items-center justify-between px-5 py-4">
    <span className="text-sm text-text-muted">{label}</span>
    {isLoading ? <Pulse className="h-4 w-28" /> : children}
  </div>
);

export default SettingsPage;
