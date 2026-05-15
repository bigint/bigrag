import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Select } from "@/components/ui/select";
import { getLegacyModelSettingsSearch } from "@/features/models/model-tabs";
import {
  DATA_SETTINGS_GROUPS,
  getSettingsFocusGroup,
  getSettingsNavItem,
  getSettingsTab,
  SETTINGS_NAV_GROUPS,
  SETTINGS_NAV_ITEMS,
  type SettingsTab,
  settingsAliasLabel,
  settingsSectionLabel,
} from "@/features/settings/settings-navigation";
import { AccountTab } from "@/features/settings/tabs/account-tab";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { ServerTab } from "@/features/settings/tabs/server-tab";
import { cn } from "@/lib/cn";

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

  const active = getSettingsNavItem(tab);
  const ActiveIcon = active.icon;
  const mobileOptions = SETTINGS_NAV_ITEMS.map((item) => {
    const Icon = item.icon;
    return {
      icon: <Icon className="size-3.5" />,
      label: settingsSectionLabel(item.value),
      value: item.value,
    };
  });

  return (
    <div className="-mt-6 -mx-4 min-h-[calc(100dvh-3rem)] bg-background md:-mx-8 lg:-mx-10">
      <header className="border-b border-border bg-background px-4 py-5 md:px-8 lg:px-10">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Operator workspace
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal">Settings</h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              Configure the instance by outcome: account access, system posture, data flow, and
              runtime policy.
            </p>
          </div>
          <div className="grid grid-cols-3 overflow-hidden rounded-md border border-border bg-card text-center text-xs">
            <SettingsHeaderMetric label="Areas" value={SETTINGS_NAV_ITEMS.length} />
            <SettingsHeaderMetric label="Runtime" value={10} />
            <SettingsHeaderMetric label="Advanced" value="hidden" />
          </div>
        </div>
        <div className="mt-4 lg:hidden">
          <Select
            aria-label="Settings section"
            onChange={setTab}
            options={mobileOptions}
            value={tab}
          />
        </div>
      </header>

      <div className="grid lg:grid-cols-[232px_minmax(0,1fr)]">
        <aside className="hidden border-r border-border bg-muted/20 lg:block">
          <div className="sticky top-0 max-h-dvh overflow-y-auto px-3 py-5">
            <nav className="flex flex-col gap-5">
              {SETTINGS_NAV_GROUPS.map((group) => (
                <div key={group.label} className="flex flex-col gap-1">
                  <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                    {group.label}
                  </div>
                  <div className="flex flex-col gap-0.5">
                    {group.items.map((item) => {
                      const isActive = item.value === tab;
                      const Icon = item.icon;
                      return (
                        <button
                          key={item.value}
                          type="button"
                          aria-current={isActive ? "page" : undefined}
                          onClick={() => setTab(item.value)}
                          className={cn(
                            "group flex min-h-8 items-center gap-2 rounded-md px-2 text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            isActive
                              ? "bg-background text-foreground shadow-sm ring-1 ring-border"
                              : "text-muted-foreground hover:bg-background/70 hover:text-foreground",
                          )}
                        >
                          <Icon
                            className={cn(
                              "size-3.5 shrink-0",
                              isActive ? "text-foreground" : "text-muted-foreground",
                            )}
                          />
                          <span className="truncate">{item.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>
          </div>
        </aside>

        <section className="min-w-0 px-4 py-5 md:px-8 lg:px-8">
          <header className="mb-5 rounded-md border border-border bg-card px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-foreground">
                  <ActiveIcon className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <h2 className="text-lg font-semibold leading-tight tracking-normal">
                      {active.label}
                    </h2>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
                      {settingsSectionLabel(active.value)}
                    </span>
                  </div>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
                    {active.description}
                  </p>
                </div>
              </div>
              {focusGroup && tab !== requestedTab && (
                <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-semibold text-muted-foreground">
                  Opened from {settingsAliasLabel(requestedTab ?? "")}
                </span>
              )}
            </div>
          </header>
          <SettingsContent focusGroup={focusGroup} tab={tab} />
        </section>
      </div>
    </div>
  );
};

const SettingsHeaderMetric = ({ label, value }: { label: string; value: number | string }) => (
  <div className="min-w-20 border-border border-r px-3 py-2 last:border-r-0">
    <div className="font-semibold text-foreground">{value}</div>
    <div className="mt-0.5 text-muted-foreground">{label}</div>
  </div>
);

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
    return <InstanceSettingsTab focusGroup={focusGroup} groups={SECURITY_SETTINGS_GROUPS} />;
  }
  if (tab === "data") {
    return <InstanceSettingsTab focusGroup={focusGroup} groups={DATA_SETTINGS_GROUPS} />;
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
