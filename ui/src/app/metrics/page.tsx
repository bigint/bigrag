"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { healthQueryOptions, metricsQueryOptions } from "@/lib/queries";

interface ParsedMetric {
  readonly name: string;
  readonly type: string;
  readonly value: string;
  readonly labels: string;
}

function parsePrometheusMetrics(text: string): readonly ParsedMetric[] {
  const metrics: ParsedMetric[] = [];
  const lines = text.split("\n");
  let currentType = "";
  for (const line of lines) {
    if (line.startsWith("# TYPE ")) {
      const parts = line.split(" ");
      currentType = parts[3] || "unknown";
    } else if (line.startsWith("#") || line.trim() === "") {
    } else {
      const match = line.match(/^([^\s{]+)(\{[^}]*\})?\s+(.+)$/);
      if (match) {
        metrics.push({
          labels: match[2] || "",
          name: match[1],
          type: currentType,
          value: match[3]
        });
      }
    }
  }
  return metrics;
}

const Pulse = ({ className }: { readonly className?: string }) => (
  <div className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`} />
);

const TYPE_COLORS: Record<string, string> = {
  counter: "bg-blue-500/10 text-blue-500",
  gauge: "bg-success/10 text-success",
  histogram: "bg-warning/10 text-warning",
  summary: "bg-purple-500/10 text-purple-500"
};

const TypeBadge = ({ type }: { readonly type: string }) => {
  const cls = TYPE_COLORS[type] || "bg-bg-hover text-text-muted";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}
    >
      {type}
    </span>
  );
};

const MetricsPage = () => {
  const [showRaw, setShowRaw] = useState(false);

  const healthQuery = useQuery(healthQueryOptions());
  const metricsQuery = useQuery(metricsQueryOptions());

  const rawMetrics = metricsQuery.data ?? "";
  const metrics = rawMetrics ? parsePrometheusMetrics(rawMetrics) : [];
  const isLoading = healthQuery.isLoading || metricsQuery.isLoading;

  const isHealthy =
    healthQuery.data?.status === "ok" || healthQuery.data?.status === "healthy";

  return (
    <div className="text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Metrics</h1>
            {metricsQuery.dataUpdatedAt > 0 && (
              <p className="mt-1 text-[13px] text-text-dim">
                Last updated{" "}
                {new Date(metricsQuery.dataUpdatedAt).toLocaleTimeString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
              onClick={() => {
                healthQuery.refetch();
                metricsQuery.refetch();
              }}
              type="button"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Error */}
        {metricsQuery.error && (
          <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {metricsQuery.error.message}
          </div>
        )}

        {/* Server Health */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Server Health
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-bg-card p-5">
              <p className="text-[13px] text-text-muted">Status</p>
              {isLoading ? (
                <Pulse className="mt-2 h-7 w-24" />
              ) : (
                <div className="mt-1 flex items-center gap-2">
                  <span
                    className={`inline-block size-2.5 rounded-full ${
                      isHealthy ? "bg-success" : "bg-danger"
                    }`}
                  />
                  <span
                    className={`text-lg font-semibold ${
                      isHealthy ? "text-success" : "text-danger"
                    }`}
                  >
                    {isHealthy ? "Healthy" : "Unhealthy"}
                  </span>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-border bg-bg-card p-5">
              <p className="text-[13px] text-text-muted">Version</p>
              {isLoading ? (
                <Pulse className="mt-2 h-7 w-28" />
              ) : (
                <p className="mt-1 font-mono text-lg font-semibold">
                  {healthQuery.data?.version || "---"}
                </p>
              )}
            </div>

            <div className="rounded-lg border border-border bg-bg-card p-5">
              <p className="text-[13px] text-text-muted">Metrics Count</p>
              {isLoading ? (
                <Pulse className="mt-2 h-7 w-20" />
              ) : (
                <p className="mt-1 font-mono text-lg font-semibold">
                  {metrics.length}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Prometheus Metrics Table */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Prometheus Metrics
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            {isLoading ? (
              <div className="divide-y divide-border">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div className="flex items-center gap-4 px-5 py-3.5" key={i}>
                    <Pulse className="h-4 w-48" />
                    <Pulse className="h-4 w-16" />
                    <Pulse className="ml-auto h-4 w-20" />
                    <Pulse className="h-4 w-32" />
                  </div>
                ))}
              </div>
            ) : metrics.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-text-dim">
                No metrics available. The server may not be exposing Prometheus
                metrics.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border text-left text-[13px] text-text-dim">
                      <th className="px-5 py-3 font-medium">Metric Name</th>
                      <th className="px-5 py-3 font-medium">Type</th>
                      <th className="px-5 py-3 font-medium">Labels</th>
                      <th className="px-5 py-3 text-right font-medium">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {metrics.map((m, i) => (
                      <tr
                        className="transition-colors hover:bg-bg-hover/50"
                        key={`${m.name}-${m.labels}-${i}`}
                      >
                        <td className="px-5 py-3 font-mono text-sm text-text">
                          {m.name}
                        </td>
                        <td className="px-5 py-3">
                          <TypeBadge type={m.type} />
                        </td>
                        <td className="max-w-[300px] truncate px-5 py-3 font-mono text-xs text-text-dim">
                          {m.labels || "---"}
                        </td>
                        <td className="px-5 py-3 text-right font-mono text-sm text-text-muted">
                          {m.value}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {!isLoading && metrics.length > 0 && (
            <p className="mt-2 text-[13px] text-text-dim">
              {metrics.length} metric{metrics.length === 1 ? "" : "s"} total
            </p>
          )}
        </div>

        {/* Raw Metrics */}
        <div>
          <button
            className="mb-4 flex items-center gap-2 text-sm font-medium text-text-muted transition-colors hover:text-text"
            onClick={() => setShowRaw(!showRaw)}
            type="button"
          >
            <svg
              className={`size-4 transition-transform ${showRaw ? "rotate-90" : ""}`}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                d="M9 5l7 7-7 7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {showRaw ? "Hide Raw" : "Show Raw"}
          </button>
          {showRaw && (
            <div className="overflow-x-auto rounded-lg border border-border bg-bg-card p-5">
              {isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 12 }).map((_, i) => (
                    <Pulse className="h-4 w-full" key={i} />
                  ))}
                </div>
              ) : rawMetrics ? (
                <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-text-muted">
                  {rawMetrics}
                </pre>
              ) : (
                <p className="text-sm text-text-dim">
                  No raw metrics data available.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MetricsPage;
