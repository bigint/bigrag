import { CheckCircle2, Cloud, Copy, KeyRound, Plug, ShieldCheck, Unplug } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import {
  useDisconnectGoogle,
  useGoogleAccount,
  useGoogleConnectorConfig,
  useUpdateGoogleConnectorConfig,
} from "@/hooks/use-google-drive";
import type { GoogleConnectorConfig } from "@/types/bigrag";

export const ConnectorsTab = () => {
  const { data: config, isPending } = useGoogleConnectorConfig();
  const { data: account } = useGoogleAccount();
  const save = useUpdateGoogleConnectorConfig();
  const disconnect = useDisconnectGoogle();
  const [enabled, setEnabled] = useState(true);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");

  useGoogleConnectorConfigDraft(config, setEnabled, setClientId);

  const configured = config?.configured ?? false;
  const callbackUrl = config?.callback_url ?? "";
  const connected = account?.connected ?? false;
  const needsReauth = account?.status === "needs_reauth";

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="overflow-hidden rounded-md border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-border border-b bg-muted/35 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-md border border-border bg-background">
              <Plug className="size-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold">Google Drive</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">OAuth connector</p>
            </div>
          </div>
          <Badge dot variant={configured ? "success" : "warning"}>
            {configured ? "configured" : "setup required"}
          </Badge>
        </div>

        <div className="flex flex-col gap-5 p-4">
          <div className="grid gap-4 md:grid-cols-3">
            <ConnectorMetric
              icon={<ShieldCheck className="size-4" />}
              label="Provider"
              value={enabled ? "Enabled" : "Disabled"}
            />
            <ConnectorMetric
              icon={<KeyRound className="size-4" />}
              label="Credentials"
              value={configured ? "Saved" : "Missing"}
            />
            <ConnectorMetric
              icon={<Cloud className="size-4" />}
              label="Account"
              value={
                connected
                  ? "Connected"
                  : needsReauth
                    ? "Reconnect"
                    : configured
                      ? "Ready"
                      : "Waiting"
              }
            />
          </div>

          <div className="rounded-md border border-border bg-background p-4">
            <Switch checked={enabled} label="Enabled" onCheckedChange={setEnabled} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="OAuth client ID"
              onChange={(e) => setClientId(e.target.value)}
              placeholder="...apps.googleusercontent.com"
              value={clientId}
            />
            <Input
              description={
                config?.has_client_secret && !clientSecret
                  ? "Leave blank to keep the current secret."
                  : undefined
              }
              label="OAuth client secret"
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={config?.has_client_secret ? "Saved" : "Client secret"}
              type="password"
              value={clientSecret}
            />
          </div>

          <div className="flex items-end gap-2">
            <Input label="OAuth callback URL" readOnly value={callbackUrl} />
            <Button
              aria-label="Copy callback URL"
              disabled={!callbackUrl}
              onClick={async () => {
                await navigator.clipboard.writeText(callbackUrl);
                toast.success("Callback URL copied");
              }}
              size="icon"
              variant="outline"
            >
              <Copy className="size-4" />
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              disabled={isPending || save.isPending}
              onClick={() =>
                save.mutate({
                  client_id: clientId,
                  client_secret: clientSecret || null,
                  enabled,
                })
              }
            >
              {save.isPending ? <Spinner /> : <CheckCircle2 className="size-4" />}
              Save connector
            </Button>
            {connected && (
              <Button
                disabled={disconnect.isPending}
                onClick={() => disconnect.mutate()}
                variant="outline"
              >
                {disconnect.isPending ? <Spinner /> : <Unplug className="size-4" />}
                Disconnect account
              </Button>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-md border border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-md border border-border bg-background">
            <Cloud className="size-5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">Connection</h3>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {connected
                ? account?.email
                : needsReauth
                  ? "Reconnect required"
                  : configured
                    ? "Ready for OAuth"
                    : "Credentials required"}
            </p>
          </div>
        </div>
        <div className="mt-5 space-y-3 text-sm">
          <ConnectorFact label="Status" value={account?.status ?? "not connected"} />
          <ConnectorFact
            label="Last connected"
            value={
              account?.last_connected_at
                ? new Date(account.last_connected_at).toLocaleString()
                : "Never"
            }
          />
          <ConnectorFact
            label="Token expiry"
            value={
              account?.token_expires_at
                ? new Date(account.token_expires_at).toLocaleString()
                : "None"
            }
          />
        </div>
      </section>
    </div>
  );
};

const ConnectorMetric = ({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) => (
  <div className="rounded-md border border-border bg-background p-3">
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      {icon}
      {label}
    </div>
    <div className="mt-2 text-sm font-semibold">{value}</div>
  </div>
);

const ConnectorFact = ({ label, value }: { label: string; value: string }) => (
  <div className="flex items-center justify-between gap-4 border-border border-b pb-3 last:border-b-0 last:pb-0">
    <span className="text-muted-foreground">{label}</span>
    <span className="min-w-0 truncate font-medium">{value}</span>
  </div>
);

const useGoogleConnectorConfigDraft = (
  config: GoogleConnectorConfig | undefined,
  setEnabled: (enabled: boolean) => void,
  setClientId: (clientId: string) => void,
) => {
  useEffect(() => {
    if (!config) return;
    setEnabled(config.enabled);
    setClientId(config.client_id);
  }, [config, setEnabled, setClientId]);
};
