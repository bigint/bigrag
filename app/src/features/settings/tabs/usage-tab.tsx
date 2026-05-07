import { useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";

type PerCollection = {
  collection: string;
  documents: number;
  chunks: number;
  storage_bytes: number;
  embedding_tokens: number;
  embedding_cost_usd_estimate: number;
  queries: number;
  avg_latency_ms: number;
};

type UsageReport = {
  window_days: number;
  queries_total: number;
  queries_per_day_avg: number;
  documents_total: number;
  chunks_total: number;
  storage_bytes_total: number;
  embedding_tokens_total: number;
  embedding_cost_usd_estimate: number;
  by_collection: PerCollection[];
};

const humanBytes = (n: number): string => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
};

export const UsageTab = () => {
  const [windowDays, setWindowDays] = useState(30);
  const queryKey = useMemo(() => ["usage", windowDays] as const, [windowDays]);
  const { data, isPending, error } = useSseSnapshotQuery<UsageReport>({
    queryKey,
    queryFn: () => apiClient.get<UsageReport>("v1/usage", { window_days: windowDays }),
    path: `v1/admin/realtime/usage?window_days=${windowDays}`,
  });

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Usage and cost</CardTitle>
          <CardDescription>
            Per-collection document, chunk, query, and embedding-cost totals. Cost is an estimate
            from a local rate card; cross-check with your provider's dashboard for the source of
            truth.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Window</span>
            <div className="w-40">
              <Select
                options={[
                  { label: "Last 7 days", value: "7" },
                  { label: "Last 30 days", value: "30" },
                  { label: "Last 90 days", value: "90" },
                  { label: "Last 365 days", value: "365" },
                ]}
                value={String(windowDays)}
                onChange={(v) => setWindowDays(Number(v))}
              />
            </div>
          </div>

          {isPending ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error instanceof Error ? error.message : "Failed to load usage."}
            </div>
          ) : data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-4">
                <StatCard label="Queries" value={data.queries_total.toLocaleString()} />
                <StatCard label="Documents" value={data.documents_total.toLocaleString()} />
                <StatCard label="Storage" value={humanBytes(data.storage_bytes_total)} />
                <StatCard
                  label="Embedding cost"
                  value={`$${data.embedding_cost_usd_estimate.toFixed(2)}`}
                />
              </div>

              <div className="overflow-hidden rounded-md border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Collection</th>
                      <th className="px-3 py-2 text-right font-medium">Docs</th>
                      <th className="px-3 py-2 text-right font-medium">Chunks</th>
                      <th className="px-3 py-2 text-right font-medium">Storage</th>
                      <th className="px-3 py-2 text-right font-medium">Tokens</th>
                      <th className="px-3 py-2 text-right font-medium">Cost</th>
                      <th className="px-3 py-2 text-right font-medium">Queries</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_collection.map((c) => (
                      <tr key={c.collection} className="border-t border-border">
                        <td className="px-3 py-2 font-mono text-xs text-foreground">
                          {c.collection}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">{c.documents}</td>
                        <td className="px-3 py-2 text-right text-xs">{c.chunks}</td>
                        <td className="px-3 py-2 text-right text-xs">
                          {humanBytes(c.storage_bytes)}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">
                          {c.embedding_tokens.toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">
                          ${c.embedding_cost_usd_estimate.toFixed(4)}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">{c.queries}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
};

const StatCard = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-md border border-border bg-card p-3">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
  </div>
);
