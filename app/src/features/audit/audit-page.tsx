import { useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { formatRelative } from "@/lib/format";
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

export const AuditPage = () => {
  const queryKey = useMemo(() => queryKeys.audit.recent(), []);
  const { data, isPending, error } = useSseSnapshotQuery<AuditList>({
    queryKey,
    queryFn: () => apiClient.get<AuditList>("v1/admin/audit", { limit: 100 }),
    path: "v1/admin/realtime/audit?limit=100",
  });

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
          )}
        </CardContent>
      </Card>
    </div>
  );
};
