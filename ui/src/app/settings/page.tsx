"use client";

import { useState, useEffect } from "react";
import { getHealth, getAdminConfig } from "@/lib/api";

function Pulse({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-[#27272a] ${className ?? ""}`}
    />
  );
}

const ENV_VARS = [
  {
    name: "NEXT_PUBLIC_BIGRAG_URL",
    description: "API base URL for the bigRAG server",
    default: "http://localhost:8080",
  },
  {
    name: "NEXT_PUBLIC_BIGRAG_API_KEY",
    description: "Bearer token for authenticating with the API",
    default: "",
  },
];

function maskValue(key: string, value: string): string {
  if (!value) return "Not set";
  if (key.toLowerCase().includes("key") || key.toLowerCase().includes("secret") || key.toLowerCase().includes("token")) {
    if (value.length <= 4) return "****";
    return value.slice(0, 4) + "****";
  }
  return value;
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [version, setVersion] = useState<string>("");
  const [latency, setLatency] = useState<number | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);

  const apiUrl =
    process.env.NEXT_PUBLIC_BIGRAG_URL || "http://localhost:8080";
  const apiKey = process.env.NEXT_PUBLIC_BIGRAG_API_KEY || "";

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const start = performance.now();
        const [health, adminConfig] = await Promise.allSettled([
          getHealth(),
          getAdminConfig(),
        ]);
        const elapsed = performance.now() - start;

        if (cancelled) return;

        if (health.status === "fulfilled") {
          setConnected(true);
          setVersion(health.value.version);
          setLatency(elapsed);
        } else {
          setConnected(false);
        }

        if (adminConfig.status === "fulfilled") {
          setConfig(adminConfig.value);
        }

        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load settings"
          );
          setConnected(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  function renderConfigValue(value: unknown): string {
    if (value === null || value === undefined) return "---";
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "number") return String(value);
    if (typeof value === "string") return value || '""';
    return JSON.stringify(value);
  }

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa]">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="mt-1 text-[13px] text-[#a1a1aa]">
            Server configuration and connection details
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {/* Section 1: Connection */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
            Connection
          </h2>
          <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
            <div className="divide-y divide-[#27272a]">
              {/* API URL */}
              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">API URL</span>
                {loading ? (
                  <Pulse className="h-4 w-48" />
                ) : (
                  <span className="font-mono text-sm text-[#fafafa]">
                    {apiUrl}
                  </span>
                )}
              </div>

              {/* Status */}
              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Status</span>
                {loading ? (
                  <Pulse className="h-4 w-28" />
                ) : (
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${
                        connected ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    <span
                      className={`text-sm font-medium ${
                        connected ? "text-green-500" : "text-red-500"
                      }`}
                    >
                      {connected ? "Connected" : "Disconnected"}
                    </span>
                  </div>
                )}
              </div>

              {/* Version */}
              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Version</span>
                {loading ? (
                  <Pulse className="h-4 w-24" />
                ) : (
                  <span className="font-mono text-sm text-[#fafafa]">
                    {version || "---"}
                  </span>
                )}
              </div>

              {/* Latency */}
              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Latency</span>
                {loading ? (
                  <Pulse className="h-4 w-20" />
                ) : (
                  <span className="font-mono text-sm text-[#fafafa]">
                    {latency !== null ? `${latency.toFixed(1)}ms` : "---"}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Server Configuration */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
            Server Configuration
          </h2>
          <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
            {loading ? (
              <div className="divide-y divide-[#27272a]">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between px-5 py-4"
                  >
                    <Pulse className="h-4 w-32" />
                    <Pulse className="h-4 w-40" />
                  </div>
                ))}
              </div>
            ) : config && Object.keys(config).length > 0 ? (
              <div className="divide-y divide-[#27272a]">
                {Object.entries(config).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between px-5 py-4"
                  >
                    <span className="text-sm text-[#a1a1aa]">{key}</span>
                    <span className="font-mono text-sm text-[#fafafa] max-w-[400px] truncate text-right">
                      {renderConfigValue(value)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-12 text-center text-sm text-[#71717a]">
                {connected === false
                  ? "Unable to fetch configuration. Server is not connected."
                  : "No configuration data available."}
              </div>
            )}
          </div>
        </div>

        {/* Section 3: Environment Variables */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
            Environment Variables
          </h2>
          <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
            <div className="divide-y divide-[#27272a]">
              {ENV_VARS.map((env) => {
                const currentValue =
                  env.name === "NEXT_PUBLIC_BIGRAG_URL"
                    ? apiUrl
                    : env.name === "NEXT_PUBLIC_BIGRAG_API_KEY"
                      ? apiKey
                      : "";

                return (
                  <div key={env.name} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="font-mono text-sm text-[#fafafa]">
                          {env.name}
                        </p>
                        <p className="mt-0.5 text-[13px] text-[#71717a]">
                          {env.description}
                        </p>
                        {env.default && (
                          <p className="mt-0.5 text-[13px] text-[#71717a]">
                            Default:{" "}
                            <span className="font-mono text-[#a1a1aa]">
                              {env.default}
                            </span>
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 font-mono text-sm text-[#a1a1aa]">
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
          <h2 className="mb-4 text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
            About
          </h2>
          <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
            <div className="divide-y divide-[#27272a]">
              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Product</span>
                <span className="text-sm font-medium text-[#fafafa]">
                  bigRAG
                </span>
              </div>

              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Version</span>
                <span className="font-mono text-sm text-[#fafafa]">
                  {version || "---"}
                </span>
              </div>

              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">License</span>
                <span className="text-sm text-[#fafafa]">Apache 2.0</span>
              </div>

              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Documentation</span>
                <a
                  href="#"
                  className="text-sm text-blue-500 hover:text-blue-400 transition-colors"
                >
                  View docs
                </a>
              </div>

              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-sm text-[#a1a1aa]">Source Code</span>
                <a
                  href="#"
                  className="text-sm text-blue-500 hover:text-blue-400 transition-colors"
                >
                  GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
