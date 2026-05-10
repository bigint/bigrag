import { CheckCircle2, Copy, Plug, Unplug } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug className="size-4" />
            Google Drive
          </CardTitle>
          <CardDescription>
            {configured ? "Configured for Google Drive OAuth." : "OAuth setup required."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
            <div>
              <div className="text-sm font-medium">Status</div>
              <div className="text-xs text-muted-foreground">
                {connected
                  ? `Connected as ${account?.email ?? "Google account"}`
                  : account?.status === "needs_reauth"
                    ? "Reconnect required"
                    : configured
                      ? "Ready for users to connect"
                      : "Not configured"}
              </div>
            </div>
            <span className="flex items-center gap-1.5 text-sm font-medium">
              {configured && <CheckCircle2 className="size-4 text-success" />}
              {configured ? "configured" : "missing"}
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Switch checked={enabled} label="Enabled" onCheckedChange={setEnabled} />
            <div className="hidden sm:block" />
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
                  enabled,
                  client_id: clientId,
                  client_secret: clientSecret || null,
                })
              }
            >
              Save Google connector
            </Button>
            {connected && (
              <Button
                disabled={disconnect.isPending}
                onClick={() => disconnect.mutate()}
                variant="outline"
              >
                <Unplug className="size-4" />
                Disconnect account
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

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
