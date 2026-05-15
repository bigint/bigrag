import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { formatNumber, formatRelative } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

type AuditEntry = {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  api_key_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
};

type AuditList = {
  entries: AuditEntry[];
  total: number;
};

const PAGE_SIZE = 25;

export const AuditPage = () => {
  const [page, setPage] = useState(0);
  const offset = page * PAGE_SIZE;
  const queryKey = useMemo(() => queryKeys.audit.list({ limit: PAGE_SIZE, offset }), [offset]);
  const { data, isPending, error } = useSseSnapshotQuery<AuditList>({
    queryKey,
    queryFn: () => apiClient.get<AuditList>("v1/admin/audit", { limit: PAGE_SIZE, offset }),
    path: `v1/admin/realtime/audit?limit=${PAGE_SIZE}&offset=${offset}`,
  });
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page + 1, pageCount);
  const firstEntry = total === 0 ? 0 : offset + 1;
  const lastEntry = Math.min(offset + (data?.entries.length ?? PAGE_SIZE), total);
  const canGoPrevious = page > 0;
  const canGoNext = offset + PAGE_SIZE < total;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        className="mb-0"
        description="Review privileged admin activity with actor, resource, request origin, and timestamp details."
        title="Audit"
      />

      <Card className="rounded-md">
        <CardHeader className="border-b border-border bg-muted/35 p-4">
          <CardTitle>Audit log</CardTitle>
          <CardDescription>
            Privileged admin actions are recorded here with actor, resource, and IP. Use this trail
            for SOC 2 and similar audits.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4">
          {isPending ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error instanceof Error ? error.message : "Failed to load audit log."}
            </div>
          ) : !data || data.entries.length === 0 ? (
            <Empty
              bordered={false}
              description="Privileged actions will start showing up here as you or an API key use them."
              title="No audit entries yet"
            />
          ) : (
            <div className="space-y-3">
              <div className="overflow-x-auto rounded-md border border-border">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">When</th>
                      <th className="px-3 py-2 text-left font-medium">Actor</th>
                      <th className="px-3 py-2 text-left font-medium">Action</th>
                      <th className="px-3 py-2 text-left font-medium">Resource</th>
                      <th className="px-3 py-2 text-left font-medium">IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.map((e) => (
                      <tr key={e.id} className="border-t border-border">
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {formatRelative(e.created_at)}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          <div className="font-medium text-foreground">{e.actor_email ?? "-"}</div>
                          {e.api_key_id && (
                            <div className="font-mono text-[10px] text-muted-foreground">
                              key {e.api_key_id.slice(0, 8)}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-foreground">{e.action}</td>
                        <td className="px-3 py-2 text-xs">
                          <div className="text-foreground">{e.resource_type}</div>
                          {e.resource_id && (
                            <div className="font-mono text-[10px] text-muted-foreground">
                              {e.resource_id.length > 24
                                ? `${e.resource_id.slice(0, 24)}...`
                                : e.resource_id}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                          {e.ip ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                <div>
                  Showing {formatNumber(firstEntry)}-{formatNumber(lastEntry)} of{" "}
                  {formatNumber(total)} entries
                </div>
                <div className="flex items-center gap-3">
                  <span>
                    Page {formatNumber(currentPage)} of {formatNumber(pageCount)}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      aria-label="Previous audit page"
                      disabled={!canGoPrevious}
                      onClick={() => setPage((value) => Math.max(0, value - 1))}
                      size="sm"
                      variant="outline"
                    >
                      <ChevronLeft className="size-4" />
                      Previous
                    </Button>
                    <Button
                      aria-label="Next audit page"
                      disabled={!canGoNext}
                      onClick={() => setPage((value) => value + 1)}
                      size="sm"
                      variant="outline"
                    >
                      Next
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
