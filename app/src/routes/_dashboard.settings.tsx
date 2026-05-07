import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { AccountTab } from "@/features/settings/tabs/account-tab";
import { AuditTab } from "@/features/settings/tabs/audit-tab";
import { ConnectorsTab } from "@/features/settings/tabs/connectors-tab";
import { ServerTab } from "@/features/settings/tabs/server-tab";
import { UsageTab } from "@/features/settings/tabs/usage-tab";

type SettingsSearch = {
  google_error?: string;
  tab?: string;
};

export const Route = createFileRoute("/_dashboard/settings")({
  validateSearch: (search: Record<string, unknown>): SettingsSearch => ({
    google_error: typeof search.google_error === "string" ? search.google_error : undefined,
    tab: typeof search.tab === "string" ? search.tab : undefined,
  }),
  component: () => <SettingsPage />,
});

const TABS = [
  { label: "Account", value: "account" },
  { label: "Server", value: "server" },
  { label: "Connectors", value: "connectors" },
  { label: "Usage & cost", value: "usage" },
  { label: "Audit log", value: "audit" },
];

const COMPONENTS: Record<string, React.FC> = {
  account: AccountTab,
  server: ServerTab,
  connectors: ConnectorsTab,
  usage: UsageTab,
  audit: AuditTab,
};

const SettingsPage = () => {
  const navigate = useNavigate();
  const search = Route.useSearch();
  const requestedTab = search.tab;
  const tab = requestedTab && COMPONENTS[requestedTab] ? requestedTab : "account";

  useEffect(() => {
    if (requestedTab === "eval") {
      navigate({ to: "/evals", replace: true });
    }
  }, [requestedTab, navigate]);

  const setTab = (value: string) => {
    navigate({
      to: "/settings",
      search: {
        ...search,
        tab: value,
      },
      replace: true,
    });
  };

  const Active = COMPONENTS[tab] ?? AccountTab;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Instance settings"
        description="Manage account, infrastructure health, and audit trails."
      />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      <div>
        <Active />
      </div>
    </div>
  );
};
