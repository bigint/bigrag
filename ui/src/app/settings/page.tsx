"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { adminConfigQueryOptions, healthQueryOptions } from "@/lib/queries";
import {
  getApiKey,
  getBaseUrl,
  setApiKey,
  setBaseUrl
} from "@/lib/auth-store";

const Pulse = ({ className }: { readonly className?: string }) => (
  <div className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`} />
);

function renderConfigValue(value: unknown): string {
  if (value === null || value === undefined) return "---";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value || '""';
  return JSON.stringify(value);
}

const SettingsPage = () => {
  const queryClient = useQueryClient();
  const healthQuery = useQuery(healthQueryOptions());
  const configQuery = useQuery(adminConfigQueryOptions());

  const [url, setUrl] = useState("");
  const [apiKey, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setUrl(getBaseUrl());
    setKey(getApiKey());
  }, []);

  const handleSave = useCallback(() => {
    setBaseUrl(url);
    setApiKey(apiKey);
    setSaved(true);
    queryClient.invalidateQueries();
    setTimeout(() => setSaved(false), 2000);
  }, [url, apiKey, queryClient]);

  const isLoading = healthQuery.isLoading || configQuery.isLoading;
  const isConnected = healthQuery.isSuccess;
  const version = healthQuery.data?.version ?? "";
  const config = configQuery.data ?? null;

  return (
    <div className="text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Server connection and configuration
          </p>
        </div>

        {/* Error */}
        {healthQuery.error && (
          <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {healthQuery.error.message}
          </div>
        )}

        {/* Section 1: Connection */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Connection
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            <div className="divide-y divide-border">
              <div className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="min-w-0">
                  <p className="text-sm text-text-muted">API URL</p>
                </div>
                <input
                  className="w-80 rounded-md border border-border bg-bg px-3 py-1.5 font-mono text-sm text-text outline-none focus:border-text-muted"
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="http://localhost:8080"
                  spellCheck={false}
                  value={url}
                />
              </div>

              <div className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="min-w-0">
                  <p className="text-sm text-text-muted">API Key</p>
                  <p className="mt-0.5 text-[13px] text-text-dim">
                    Master key or admin API key
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    className="w-80 rounded-md border border-border bg-bg px-3 py-1.5 font-mono text-sm text-text outline-none focus:border-text-muted"
                    onChange={(e) => setKey(e.target.value)}
                    placeholder="br_..."
                    spellCheck={false}
                    type={showKey ? "text" : "password"}
                    value={apiKey}
                  />
                  <button
                    className="shrink-0 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-muted hover:bg-bg-hover"
                    onClick={() => setShowKey(!showKey)}
                    type="button"
                  >
                    {showKey ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between px-5 py-4">
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
                  {version && (
                    <span className="ml-2 font-mono text-xs text-text-dim">
                      v{version}
                    </span>
                  )}
                </div>
                <button
                  className="rounded-md bg-text px-4 py-1.5 text-sm font-medium text-bg hover:opacity-90"
                  onClick={handleSave}
                  type="button"
                >
                  {saved ? "Saved" : "Save & Reconnect"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Server Configuration */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Server Configuration
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            {isLoading ? (
              <div className="divide-y divide-border">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    className="flex items-center justify-between px-5 py-4"
                    key={i}
                  >
                    <Pulse className="h-4 w-32" />
                    <Pulse className="h-4 w-40" />
                  </div>
                ))}
              </div>
            ) : config && Object.keys(config).length > 0 ? (
              <div className="divide-y divide-border">
                {Object.entries(config).map(([key, value]) => (
                  <div
                    className="flex items-center justify-between px-5 py-4"
                    key={key}
                  >
                    <span className="text-sm text-text-muted">{key}</span>
                    <span className="max-w-[400px] truncate text-right font-mono text-sm text-text">
                      {renderConfigValue(value)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-12 text-center text-sm text-text-dim">
                {isConnected
                  ? "No configuration data available."
                  : "Unable to fetch configuration. Server is not connected."}
              </div>
            )}
          </div>
        </div>

        {/* Section 3: About */}
        <div>
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            About
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            <div className="divide-y divide-border">
              <SettingsRow isLoading={false} label="Product">
                <span className="text-sm font-medium text-text">bigRAG</span>
              </SettingsRow>
              <SettingsRow isLoading={false} label="Version">
                <span className="font-mono text-sm text-text">
                  {version || "---"}
                </span>
              </SettingsRow>
              <SettingsRow isLoading={false} label="License">
                <span className="text-sm text-text">Apache 2.0</span>
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
