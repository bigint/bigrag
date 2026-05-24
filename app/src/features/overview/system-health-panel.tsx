import { ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { cn } from "@/lib/cn";

export type HealthService = {
  detail?: string;
  label: string;
  ok: boolean | undefined;
};

interface SystemHealthPanelProps {
  readonly services: HealthService[];
  readonly status: string | undefined;
}

export const SystemHealthPanel = ({ services, status }: SystemHealthPanelProps) => (
  <Panel>
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold">System health</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Readiness of storage, vector search, cache, and embedding calls.
        </p>
      </div>
      <Badge variant={status === "ok" ? "success" : "warning"} dot>
        {status ?? "checking"}
      </Badge>
    </div>
    <div className="mt-4 space-y-2">
      {services.map((service) => (
        <HealthRow
          detail={service.detail}
          key={service.label}
          label={service.label}
          ok={service.ok}
        />
      ))}
    </div>
  </Panel>
);

const HealthRow = ({
  detail,
  label,
  ok,
}: {
  detail?: string;
  label: string;
  ok: boolean | undefined;
}) => (
  <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted/60 px-3 py-2.5">
    <div className="flex min-w-0 items-center gap-2">
      <ShieldCheck
        className={cn(
          "size-4 shrink-0",
          ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
        )}
      />
      <span className="truncate text-sm font-semibold">{label}</span>
    </div>
    <span
      className={cn(
        "shrink-0 text-xs font-semibold",
        ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
      )}
      title={detail}
    >
      {ok === undefined ? "checking" : ok ? "online" : "degraded"}
    </span>
  </div>
);
