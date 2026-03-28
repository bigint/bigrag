"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getHealth, getMetrics } from "@/lib/api";

interface ParsedMetric {
  name: string;
  type: string;
  value: string;
  labels: string;
}

function parsePrometheusMetrics(text: string): ParsedMetric[] {
  const metrics: ParsedMetric[] = [];
  const lines = text.split("\n");
  let currentType = "";
  for (const line of lines) {
    if (line.startsWith("# TYPE ")) {
      const parts = line.split(" ");
      currentType = parts[3] || "unknown";
    } else if (line.startsWith("#") || line.trim() === "") {
      continue;
    } else {
      const match = line.match(/^([^\s{]+)(\{[^}]*\})?\s+(.+)$/);
      if (match) {
        metrics.push({
          name: match[1],
          type: currentType,
          value: match[3],
          labels: match[2] || "",
        });
      }
    }
  }
  return metrics;
}

function Pulse({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-[#27272a] ${className ?? ""}`}
    />
  );
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    counter: "bg-blue-500/10 text-blue-500",
    gauge: "bg-green-500/10 text-green-500",
    histogram: "bg-yellow-500/10 text-yellow-500",
    summary: "bg-purple-500/10 text-purple-500",
  };
  const cls = colors[type] || "bg-[#27272a] text-[#a1a1aa]";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}
    >
      {type}
    </span>
  );
}

export default function MetricsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [version, setVersion] = useState<string>("");
  const [latency, setLatency] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<ParsedMetric[]>([]);
  const [rawMetrics, setRawMetrics] = useState<string>("");
  const [showRaw, setShowRaw] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const start = performance.now();
      const [health, metricsText] = await Promise.allSettled([
        getHealth(),
        getMetrics(),
      ]);
      const elapsed = performance.now() - start;

      if (health.status === "fulfilled") {
        setStatus(health.value.status);
        setVersion(health.value.version);
        setLatency(elapsed);
      } else {
        setStatus("error");
        setVersion("");
        setLatency(null);
      }

      if (metricsText.status === "fulfilled") {
        setRawMetrics(metricsText.value);
        setMetrics(parsePrometheusMetrics(metricsText.value));
      } else {
        setRawMetrics("");
        setMetrics([]);
      }

      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchData, 10000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, fetchData]);

  const healthy = status === "ok" || status === "healthy";

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa]">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Metrics</h1>
            {lastUpdated && (
              <p className="mt-1 text-[13px] text-[#71717a]">
                Last updated {lastUpdated.toLocaleTimeString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-[#a1a1aa] cursor-pointer select-none">
              <button
                type="button"
                role="switch"
                aria-checked={autoRefresh}
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                  autoRefresh ? "bg-blue-500" : "bg-[#27272a]"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                    autoRefresh ? "translate-x-[18px]" : "translate-x-[3px]"
                  }`}
                />
              </button>
              Auto-refresh
            </label>
            <button
              onClick={() => {
                setLoading(true);
                fetchData();
              }}
              className="bg-blue-500 hover:bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {/* Server Health */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
            Server Health
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
              <p className="text-[13px] text-[#a1a1aa]">Status</p>
              {loading ? (
                <Pulse className="mt-2 h-7 w-24" />
              ) : (
                <div className="mt-1 flex items-center gap-2">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      healthy ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span
                    className={`text-lg font-semibold ${
                      healthy ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {healthy ? "Healthy" : "Unhealthy"}
                  </span>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
              <p className="text-[13px] text-[#a1a1aa]">Version</p>
              {loading ? (
                <Pulse className="mt-2 h-7 w-28" />
              ) : (
                <p className="mt-1 text-lg font-semibold font-mono">
                  {version || "---"}
                </p>
              )}
            </div>

            <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
              <p className="text-[13px] text-[#a1a1aa]">Latency</p>
              {loading ? (
                <Pulse className="mt-2 h-7 w-20" />
              ) : (
                <p className="mt-1 text-lg font-semibold font-mono">
                  {latency !== null ? `${latency.toFixed(1)}ms` : "---"}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Prometheus Metrics Table */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
            Prometheus Metrics
          </h2>
          <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
            {loading ? (
              <div className="divide-y divide-[#27272a]">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4 px-5 py-3.5">
                    <Pulse className="h-4 w-48" />
                    <Pulse className="h-4 w-16" />
                    <Pulse className="h-4 w-20 ml-auto" />
                    <Pulse className="h-4 w-32" />
                  </div>
                ))}
              </div>
            ) : metrics.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-[#71717a]">
                No metrics available. The server may not be exposing Prometheus
                metrics.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#27272a] text-left text-[13px] text-[#71717a]">
                      <th className="px-5 py-3 font-medium">Metric Name</th>
                      <th className="px-5 py-3 font-medium">Type</th>
                      <th className="px-5 py-3 font-medium">Labels</th>
                      <th className="px-5 py-3 font-medium text-right">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#27272a]">
                    {metrics.map((m, i) => (
                      <tr
                        key={`${m.name}-${m.labels}-${i}`}
                        className="hover:bg-[#27272a]/50 transition-colors"
                      >
                        <td className="px-5 py-3 font-mono text-sm text-[#fafafa]">
                          {m.name}
                        </td>
                        <td className="px-5 py-3">
                          <TypeBadge type={m.type} />
                        </td>
                        <td className="px-5 py-3 font-mono text-xs text-[#71717a] max-w-[300px] truncate">
                          {m.labels || "---"}
                        </td>
                        <td className="px-5 py-3 text-right font-mono text-sm text-[#a1a1aa]">
                          {m.value}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {!loading && metrics.length > 0 && (
            <p className="mt-2 text-[13px] text-[#71717a]">
              {metrics.length} metric{metrics.length !== 1 ? "s" : ""} total
            </p>
          )}
        </div>

        {/* Raw Metrics */}
        <div>
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="mb-4 flex items-center gap-2 text-sm font-medium text-[#a1a1aa] hover:text-[#fafafa] transition-colors"
          >
            <svg
              className={`h-4 w-4 transition-transform ${
                showRaw ? "rotate-90" : ""
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 5l7 7-7 7"
              />
            </svg>
            {showRaw ? "Hide Raw" : "Show Raw"}
          </button>
          {showRaw && (
            <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5 overflow-x-auto">
              {loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 12 }).map((_, i) => (
                    <Pulse key={i} className="h-4 w-full" />
                  ))}
                </div>
              ) : rawMetrics ? (
                <pre className="font-mono text-xs text-[#a1a1aa] whitespace-pre-wrap break-all leading-relaxed">
                  {rawMetrics}
                </pre>
              ) : (
                <p className="text-sm text-[#71717a]">
                  No raw metrics data available.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
