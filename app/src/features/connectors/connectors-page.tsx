import { CheckCircle2, Copy, KeyRound, Plug, ShieldCheck, Unplug } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tabs } from "@/components/ui/tabs";
import {
  type ConnectorProvider,
  type ConnectorProviderId,
  type ConnectorStatus,
  connectorProviderById,
  connectorProviders,
  connectorStatus,
  defaultConnectorProvider,
} from "@/features/connectors/connector-catalog";
import {
  useDisconnectGoogle,
  useGoogleAccount,
  useGoogleConnectorConfig,
  useUpdateGoogleConnectorConfig,
} from "@/hooks/use-google-drive";
import { cn } from "@/lib/cn";
import type { GoogleAccount, GoogleConnectorConfig } from "@/types/bigrag";

const CONNECTOR_PROVIDER_TABS = connectorProviders.map((provider) => ({
  icon: provider.icon,
  label: provider.label,
  value: provider.id,
}));

export const ConnectorsPage = () => {
  const { data: config, isPending } = useGoogleConnectorConfig();
  const { data: account } = useGoogleAccount();
  const save = useUpdateGoogleConnectorConfig();
  const disconnect = useDisconnectGoogle();
  const [selectedProviderId, setSelectedProviderId] = useState<ConnectorProviderId>(
    defaultConnectorProvider.id,
  );
  const [enabled, setEnabled] = useState(true);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");

  useGoogleConnectorConfigDraft(config, setEnabled, setClientId);

  const selectedProvider = connectorProviderById(selectedProviderId);
  const configured = config?.configured ?? false;
  const callbackUrl = config?.callback_url ?? "";
  const connected = account?.connected ?? false;
  const needsReauth = account?.status === "needs_reauth";
  const googleStatus = connectorStatus({
    availability: "available",
    configured,
    connected,
    enabled,
    needsReauth,
  });
  const selectedStatus =
    selectedProvider.id === "google-drive"
      ? googleStatus
      : connectorStatus({ availability: selectedProvider.availability });
  const setProviderTab = (value: string) => setSelectedProviderId(value as ConnectorProviderId);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        className="mb-0"
        description="Manage provider credentials, account state, and collection source access from one connector catalog."
        title="Connectors"
      />

      <Tabs onChange={setProviderTab} tabs={CONNECTOR_PROVIDER_TABS} value={selectedProvider.id} />

      <section className="overflow-hidden rounded-md border border-border bg-card">
        <ProviderHeader provider={selectedProvider} status={selectedStatus} />
        {selectedProvider.availability === "available" ? (
          <GoogleConnectorPanel
            account={account}
            callbackUrl={callbackUrl}
            clientId={clientId}
            clientSecret={clientSecret}
            config={config}
            configured={configured}
            connected={connected}
            disconnecting={disconnect.isPending}
            enabled={enabled}
            isPending={isPending}
            needsReauth={needsReauth}
            onClientIdChange={setClientId}
            onClientSecretChange={setClientSecret}
            onDisconnect={() => disconnect.mutate()}
            onEnabledChange={setEnabled}
            onSave={() =>
              save.mutate({
                client_id: clientId,
                client_secret: clientSecret || null,
                enabled,
              })
            }
            provider={selectedProvider}
            saving={save.isPending}
          />
        ) : (
          <PlannedConnectorPanel provider={selectedProvider} />
        )}
      </section>
    </div>
  );
};

const ProviderHeader = ({
  provider,
  status,
}: {
  provider: ConnectorProvider;
  status: ConnectorStatus;
}) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-border border-b bg-muted/35 px-4 py-3">
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-md border border-border bg-background">
        <ProviderIcon provider={provider} />
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">{provider.label}</h2>
          <Badge variant="neutral">{provider.category}</Badge>
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">{status.detail}</p>
      </div>
    </div>
    <Badge dot variant={status.variant}>
      {status.label}
    </Badge>
  </div>
);

const GoogleConnectorPanel = ({
  account,
  callbackUrl,
  clientId,
  clientSecret,
  config,
  configured,
  connected,
  disconnecting,
  enabled,
  isPending,
  needsReauth,
  onClientIdChange,
  onClientSecretChange,
  onDisconnect,
  onEnabledChange,
  onSave,
  provider,
  saving,
}: {
  account: GoogleAccount | undefined;
  callbackUrl: string;
  clientId: string;
  clientSecret: string;
  config: GoogleConnectorConfig | undefined;
  configured: boolean;
  connected: boolean;
  disconnecting: boolean;
  enabled: boolean;
  isPending: boolean;
  needsReauth: boolean;
  onClientIdChange: (value: string) => void;
  onClientSecretChange: (value: string) => void;
  onDisconnect: () => void;
  onEnabledChange: (enabled: boolean) => void;
  onSave: () => void;
  provider: ConnectorProvider;
  saving: boolean;
}) => (
  <div className="flex flex-col gap-5 p-4">
    <ProviderReadinessGrid
      configured={configured}
      connected={connected}
      enabled={enabled}
      needsReauth={needsReauth}
    />

    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="flex flex-col gap-4">
        <div className="rounded-md border border-border bg-background p-4">
          <Switch checked={enabled} label="Enabled" onCheckedChange={onEnabledChange} />
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Provider setup
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Save OAuth credentials, register the callback URL in the provider console, then connect
            a user account from a collection source browser.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="OAuth client ID"
            onChange={(event) => onClientIdChange(event.target.value)}
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
            onChange={(event) => onClientSecretChange(event.target.value)}
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
          <Button disabled={isPending || saving} onClick={onSave}>
            {saving ? <Spinner /> : <CheckCircle2 className="size-4" />}
            Save provider
          </Button>
          {connected && (
            <Button disabled={disconnecting} onClick={onDisconnect} variant="outline">
              {disconnecting ? <Spinner /> : <Unplug className="size-4" />}
              Disconnect account
            </Button>
          )}
        </div>
      </div>

      <ProviderStatePanel
        account={account}
        configured={configured}
        connected={connected}
        needsReauth={needsReauth}
        provider={provider}
      />
    </div>
  </div>
);

const ProviderReadinessGrid = ({
  configured,
  connected,
  enabled,
  needsReauth,
}: {
  configured: boolean;
  connected: boolean;
  enabled: boolean;
  needsReauth: boolean;
}) => (
  <div className="grid overflow-hidden rounded-md border border-border md:grid-cols-3 md:divide-x md:divide-border">
    <ReadinessItem
      icon={<ShieldCheck className="size-4" />}
      label="Provider"
      value={enabled ? "Enabled" : "Disabled"}
    />
    <ReadinessItem
      icon={<KeyRound className="size-4" />}
      label="Credentials"
      value={configured ? "Saved" : "Missing"}
    />
    <ReadinessItem
      icon={<Plug className="size-4" />}
      label="Account"
      value={connected ? "Connected" : needsReauth ? "Reconnect" : configured ? "Ready" : "Waiting"}
    />
  </div>
);

const ReadinessItem = ({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) => (
  <div className="border-border border-b bg-background p-3 last:border-b-0 md:border-b-0">
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      {icon}
      {label}
    </div>
    <div className="mt-2 text-sm font-semibold">{value}</div>
  </div>
);

const ProviderStatePanel = ({
  account,
  configured,
  connected,
  needsReauth,
  provider,
}: {
  account: GoogleAccount | undefined;
  configured: boolean;
  connected: boolean;
  needsReauth: boolean;
  provider: ConnectorProvider;
}) => (
  <div className="rounded-md border border-border bg-background p-4">
    <div className="flex items-center gap-3">
      <div className="flex size-10 shrink-0 items-center justify-center rounded-md border border-border bg-card">
        <ProviderIcon provider={provider} />
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
      <ProviderFact label="Status" value={account?.status ?? "not connected"} />
      <ProviderFact
        label="Last connected"
        value={
          account?.last_connected_at ? formatConnectorDate(account.last_connected_at) : "Never"
        }
      />
      <ProviderFact
        label="Token expiry"
        value={account?.token_expires_at ? formatConnectorDate(account.token_expires_at) : "None"}
      />
    </div>
  </div>
);

const PlannedConnectorPanel = ({ provider }: { provider: ConnectorProvider }) => (
  <div className="grid gap-5 p-4 lg:grid-cols-2">
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Setup path
      </div>
      <RequirementList items={provider.setupItems} />
    </div>
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Source operations
      </div>
      <CapabilityList items={provider.capabilities} />
    </div>
  </div>
);

const RequirementList = ({ items }: { items: readonly string[] }) => (
  <div className="mt-3 overflow-hidden rounded-md border border-border bg-background">
    {items.map((item) => (
      <div
        className="flex items-center gap-2 border-border border-b px-3 py-3 text-sm last:border-b-0"
        key={item}
      >
        <CheckCircle2 className="size-4 text-muted-foreground" />
        <span className="font-medium">{item}</span>
      </div>
    ))}
  </div>
);

const CapabilityList = ({ items }: { items: readonly string[] }) => (
  <div className="mt-3 flex flex-wrap gap-2">
    {items.map((item) => (
      <Badge key={item} variant="neutral">
        {item}
      </Badge>
    ))}
  </div>
);

const ProviderIcon = ({
  className,
  provider,
}: {
  className?: string;
  provider: ConnectorProvider;
}) => {
  const Icon = provider.icon;
  return <Icon className={cn("size-5", className)} />;
};

const ProviderFact = ({ label, value }: { label: string; value: string }) => (
  <div className="flex items-center justify-between gap-4 border-border border-b pb-3 last:border-b-0 last:pb-0">
    <span className="text-muted-foreground">{label}</span>
    <span className="min-w-0 truncate font-medium">{value}</span>
  </div>
);

const formatConnectorDate = (value: string) => new Date(value).toLocaleString();

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
