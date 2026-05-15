import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { PageHeader } from "@/components/ui/page-header";
import { PageShell } from "@/components/ui/page-shell";
import { Tabs } from "@/components/ui/tabs";
import {
  DATA_SETTINGS_GROUPS,
  getSettingsTab,
  SECURITY_SETTINGS_KEYS,
  SETTINGS_NAV_ITEMS,
  type SettingsTab,
} from "@/features/settings/settings-navigation";
import { AccountTab } from "@/features/settings/tabs/account-tab";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { ServerTab } from "@/features/settings/tabs/server-tab";

type SettingsSearch = {
  tab?: string;
};

export const Route = createFileRoute("/_dashboard/settings")({
  validateSearch: (search: Record<string, unknown>): SettingsSearch => ({
    tab: typeof search.tab === "string" ? search.tab : undefined,
  }),
  component: () => <SettingsPage />,
});

const SECURITY_SETTINGS_GROUPS = ["security"] as const;
const SETTINGS_TABS = SETTINGS_NAV_ITEMS.map(({ icon, label, value }) => ({ icon, label, value }));

const SettingsPage = () => {
  const navigate = useNavigate();
  const search = Route.useSearch();
  const requestedTab = search.tab;
  const tab = getSettingsTab(requestedTab);

  const setTab = (value: string) =>
    navigate({
      to: "/settings",
      search: { tab: value },
      replace: true,
    });

  return (
    <PageShell>
      <PageHeader
        className="mb-0"
        description="Manage account access, platform health, security policy, and data flow without leaving the operator console."
        title="Settings"
      />

      <Tabs onChange={setTab} tabs={SETTINGS_TABS} value={tab} />

      <section className="flex min-w-0 flex-col">
        <SettingsContent tab={tab} />
      </section>
    </PageShell>
  );
};

const SettingsContent = ({ tab }: { tab: SettingsTab }) => {
  if (tab === "account") return <AccountTab />;
  if (tab === "health") return <ServerTab />;
  if (tab === "security") {
    return (
      <InstanceSettingsTab
        groups={SECURITY_SETTINGS_GROUPS}
        includeKeys={SECURITY_SETTINGS_KEYS}
        stacked
      />
    );
  }
  if (tab === "data") {
    return <InstanceSettingsTab groups={DATA_SETTINGS_GROUPS} stacked />;
  }
  return <AccountTab />;
};
