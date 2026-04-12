"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { apiClient } from "@/lib/api";
import { formatRelative } from "@/lib/format";

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

export const AuditTab = () => {
  const { data, isPending, error } = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => apiClient.get<AuditList>("v1/admin/audit", { limit: 100 }),
    refetchInterval: 60_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit log</CardTitle>
        <CardDescription>
          Privileged admin actions are recorded here with actor, resource, and IP. Used for
          compliance trails (SOC2 / similar) — retained indefinitely until manually purged.
        </CardDescription>
      </CardHeader>
      <CardContent>
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
            description="Privileged actions will start showing up here as you (or an API key) use them."
            title="No audit entries yet"
          />
        ) : (
          <div className="overflow-hidden rounded-md border border-border">
            <table className="w-full text-sm">
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
                      <div className="font-medium text-foreground">{e.actor_email ?? "—"}</div>
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
                            ? `${e.resource_id.slice(0, 24)}…`
                            : e.resource_id}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {e.ip ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
