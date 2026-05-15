import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { getLegacyModelSettingsSearch } from "@/features/models/model-tabs";
import {
  DATA_SETTINGS_GROUPS,
  getSettingsFocusGroup,
  getSettingsTab,
  SETTINGS_NAV_ITEMS,
  type SettingsTab,
} from "@/features/settings/settings-navigation";
import { AccountTab } from "@/features/settings/tabs/account-tab";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { ServerTab } from "@/features/settings/tabs/server-tab";

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

const SECURITY_SETTINGS_GROUPS = ["security"] as const;
const SETTINGS_TABS = SETTINGS_NAV_ITEMS.map(({ icon, label, value }) => ({ icon, label, value }));

const SettingsPage = () => {
  const navigate = useNavigate();
  const search = Route.useSearch();
  const requestedTab = search.tab;
  const tab = getSettingsTab(requestedTab);
  const focusGroup = getSettingsFocusGroup(requestedTab);

  useRedirectLegacySettingsTab(search, navigate);

  const setTab = (value: string) =>
    navigate({
      to: "/settings",
      search: { ...search, tab: value },
      replace: true,
    });

  return (
    <div className="flex w-full flex-col gap-6">
      <PageHeader
        className="mb-0"
        description="Manage account access, platform health, security policy, and data flow without leaving the operator console."
        title="Settings"
      />

      <Tabs onChange={setTab} tabs={SETTINGS_TABS} value={tab} />

      <section className="flex min-w-0 flex-col">
        <SettingsContent focusGroup={focusGroup} tab={tab} />
      </section>
    </div>
  );
};

const SettingsContent = ({
  focusGroup,
  tab,
}: {
  focusGroup: ReturnType<typeof getSettingsFocusGroup>;
  tab: SettingsTab;
}) => {
  if (tab === "account") return <AccountTab />;
  if (tab === "health") return <ServerTab />;
  if (tab === "security") {
    return (
      <InstanceSettingsTab focusGroup={focusGroup} groups={SECURITY_SETTINGS_GROUPS} stacked />
    );
  }
  if (tab === "data") {
    return <InstanceSettingsTab focusGroup={focusGroup} groups={DATA_SETTINGS_GROUPS} stacked />;
  }
  return <AccountTab />;
};

const useRedirectLegacySettingsTab = (
  search: SettingsSearch,
  navigate: ReturnType<typeof useNavigate>,
) => {
  useEffect(() => {
    const requestedTab = search.tab;
    const modelSettingsSearch = getLegacyModelSettingsSearch(requestedTab);
    if (modelSettingsSearch) {
      navigate({ to: "/models", search: modelSettingsSearch, replace: true });
      return;
    }
    if (requestedTab === "eval") {
      navigate({ to: "/evals", replace: true });
      return;
    }
    if (requestedTab === "backups") {
      navigate({ to: "/backups", replace: true });
      return;
    }
    if (requestedTab === "vector_store") {
      navigate({ to: "/vector-storage", replace: true });
      return;
    }
    if (requestedTab === "usage") {
      navigate({ to: "/usage", replace: true });
      return;
    }
    if (requestedTab === "audit") {
      navigate({ to: "/audit", replace: true });
      return;
    }
    if (requestedTab === "connectors") {
      navigate({
        to: "/connectors",
        search: search.google_error ? { google_error: search.google_error } : {},
        replace: true,
      });
    }
  }, [search, navigate]);
};
