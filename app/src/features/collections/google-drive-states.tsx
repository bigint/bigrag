import { Button } from "@atelier/ui";
import { Cloud, Settings, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

export const SetupRequired = () => (
  <ConnectorState
    action={
      <Button
        onClick={() => {
          window.location.href = "/connectors";
        }}
      >
        <Settings className="size-4" />
        Connectors
      </Button>
    }
    icon={<Settings className="size-5" />}
    label="Connector setup required"
    value="Add Google OAuth credentials in Connectors."
  />
);

export const ConnectRequired = ({
  email,
  needsReauth,
  onConnect,
}: {
  email: string | null | undefined;
  needsReauth: boolean;
  onConnect: () => void;
}) => (
  <ConnectorState
    action={<Button onClick={onConnect}>{needsReauth ? "Reconnect" : "Connect Google"}</Button>}
    icon={needsReauth ? <TriangleAlert className="size-5" /> : <Cloud className="size-5" />}
    label={needsReauth ? "Reconnect Google Drive" : "Connect Google Drive"}
    value={email ?? "Authorize Drive read access."}
  />
);

const ConnectorState = ({
  action,
  icon,
  label,
  value,
}: {
  action: ReactNode;
  icon: ReactNode;
  label: string;
  value: string;
}) => (
  <div className="rounded-sm border border-border bg-card p-5">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-sm border border-border bg-background">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold">{label}</div>
          <div className="mt-0.5 truncate text-xs text-muted-foreground">{value}</div>
        </div>
      </div>
      {action}
    </div>
  </div>
);
