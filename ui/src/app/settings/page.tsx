"use client";

import { useQuery } from "@tanstack/react-query";
import { adminConfigQueryOptions, healthQueryOptions } from "@/lib/queries";

const Pulse = ({ className }: { readonly className?: string }) => (
  <div className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`} />
);

const ENV_VARS = [
  {
    default: "http://localhost:8080",
    description: "API base URL for the bigRAG server",
    name: "NEXT_PUBLIC_BIGRAG_URL"
  },
  {
    default: "",
    description: "Bearer token for authenticating with the API",
    name: "NEXT_PUBLIC_BIGRAG_API_KEY"
  }
] as const;

function maskValue(key: string, value: string): string {
  if (!value) return "Not set";
  const lowerKey = key.toLowerCase();
  if (
    lowerKey.includes("key") ||
    lowerKey.includes("secret") ||
    lowerKey.includes("token")
  ) {
    return value.length <= 4 ? "****" : `${value.slice(0, 4)}****`;
  }
  return value;
}

function renderConfigValue(value: unknown): string {
  if (value === null || value === undefined) return "---";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value || '""';
  return JSON.stringify(value);
}

const SettingsPage = () => {
  const healthQuery = useQuery(healthQueryOptions());
  const configQuery = useQuery(adminConfigQueryOptions());

  const isLoading = healthQuery.isLoading || configQuery.isLoading;
  const isConnected = healthQuery.isSuccess;
  const version = healthQuery.data?.version ?? "";
  const config = configQuery.data ?? null;

  const apiUrl = process.env.NEXT_PUBLIC_BIGRAG_URL || "http://localhost:8080";
  const apiKey = process.env.NEXT_PUBLIC_BIGRAG_API_KEY || "";

  return (
    <div className="text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Server configuration and connection details
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
              <SettingsRow isLoading={isLoading} label="API URL">
                <span className="font-mono text-sm text-text">{apiUrl}</span>
              </SettingsRow>

              <SettingsRow isLoading={isLoading} label="Status">
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
              </SettingsRow>

              <SettingsRow isLoading={isLoading} label="Version">
                <span className="font-mono text-sm text-text">
                  {version || "---"}
                </span>
              </SettingsRow>
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

        {/* Section 3: Environment Variables */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Environment Variables
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            <div className="divide-y divide-border">
              {ENV_VARS.map((env) => {
                const currentValue =
                  env.name === "NEXT_PUBLIC_BIGRAG_URL"
                    ? apiUrl
                    : env.name === "NEXT_PUBLIC_BIGRAG_API_KEY"
                      ? apiKey
                      : "";

                return (
                  <div className="px-5 py-4" key={env.name}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="font-mono text-sm text-text">
                          {env.name}
                        </p>
                        <p className="mt-0.5 text-[13px] text-text-dim">
                          {env.description}
                        </p>
                        {env.default && (
                          <p className="mt-0.5 text-[13px] text-text-dim">
                            Default:{" "}
                            <span className="font-mono text-text-muted">
                              {env.default}
                            </span>
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 font-mono text-sm text-text-muted">
                        {maskValue(env.name, currentValue)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Section 4: About */}
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
